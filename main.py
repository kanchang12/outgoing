from flask import Flask, render_template, request, jsonify
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Gather, Say
from openai import OpenAI
from flask_socketio import SocketIO, emit
from engineio.payload import Payload
import PyPDF2
import re
import json
from datetime import datetime
import os
import asyncio
import websockets
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
Payload.max_decode_packets = 50
socketio = SocketIO(app, 
                   cors_allowed_origins="*",
                   async_mode='eventlet',
                   ping_timeout=60,
                   ping_interval=25,
                   max_http_buffer_size=1e8)

# Initialize clients
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
twilio_client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))

# Create thread pool for async operations
executor = ThreadPoolExecutor(max_workers=10)

# NEW: WebSocket connections dictionary
ws_connections = {}

def clean_text(text):
    """Clean extracted text from PDF"""
    text = re.sub(r'\xa0 Page \d+ of \d+\xa0 \xa0', '', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def extract_text_from_pdf(pdf_path):
    """Extract and clean text from PDF file"""
    with open(pdf_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
    return clean_text(text)

def parse_resume(pdf_text):
    """Parse relevant information from PDF text"""
    experience = re.findall(r'Experience(.*?)Education', pdf_text, re.DOTALL)
    skills = re.findall(r'Skills(.*?)Experience', pdf_text, re.DOTALL)
    education = re.findall(r'Education(.*?)$', pdf_text, re.DOTALL)
    
    return {
        'experience': clean_text(experience[0] if experience else ''),
        'skills': clean_text(skills[0] if skills else ''),
        'education': clean_text(education[0] if education else '')
    }

# Read and parse PDF at startup
PDF_PATH = "Profile.pdf"
pdf_text = extract_text_from_pdf(PDF_PATH)
parsed_resume = parse_resume(pdf_text)

# Keep your existing SYSTEM_PROMPT
# Updated system prompt
SYSTEM_PROMPT = """
You are James, a professional HR consultant conducting a phone conversation about a candidate for an AI Developer (Freelance) position.

Key Skills of the candidate:
{skills}

Recent Experience:
{experience}

Education:
{education}

Core Personality Traits:
- Professional and articulate
- Knowledgeable about AI development
- Enthusiastic about the candidate's qualifications
- Attentive to the employer's needs

Focus Areas:
1. AI and automation experience
2. Python development skills
3. Chatbot development expertise
4. Technical project experience
5. Problem-solving abilities

You must behave like an HR consultant having a conversation about the candidate's profile. You should prioritize clarity, empathy, and professionalism at all times.

### Interruptions:
If the user interrupts or expresses frustration, **pause immediately** and acknowledge their statement in a respectful manner. If the user says something like:
- **"I’m busy"**: Acknowledge their time constraints and offer to follow up later.
  - Example: "I understand you are busy, would it be better if we scheduled another time to discuss?"
  
- **"Tell me more"**: Continue providing details in a concise, relevant manner.
  - Example: "Certainly! The candidate has experience working with large-scale AI systems, specializing in NLP and automation."

- **"Where did you get my number?"**: Politely explain that the number was provided through an official recruitment platform or company database.
  - Example: "I got your number through the recruitment platform we are using to contact potential employers about exciting opportunities."

- **"Stop calling"**: Apologize and stop the conversation.
  - Example: "I’m really sorry for any inconvenience. I’ll make sure to stop calling."

- **"Can you call back later?"**: Politely acknowledge the request and offer to call at a more convenient time.
  - Example: "Of course! When would be a better time for me to reach you?"

### Handling Long Pauses:
If the user goes silent for more than 5 seconds, prompt them with a gentle follow-up, showing that you are still available to continue the conversation.

Example:
- "I’m here if you’d like to continue our conversation."

### Keep the conversation flowing:
- Provide brief summaries of key points after each AI response to maintain context.
- After a question or if the user seems confused, rephrase in simpler terms if necessary.
- Always keep the focus on the candidate's skills, experience, and qualifications unless the employer asks for more personal details.

### Additional Phrases to Handle:
- **"Can I call you later?"**: Acknowledge and ask for their preferred time to continue.
  - Example: "Certainly! What time works best for you?"

- **"I’m not interested"**: Respect their decision and close the conversation politely.
  - Example: "I respect that. Thank you for your time, and feel free to reach out if anything changes."

- **"Are you recording this call?"**: Assure them of transparency and explain the purpose of the recording.
  - Example: "Yes, we are recording this for training and quality purposes, but you can request to stop the recording at any time."

- **"What’s the position?"**: Provide a brief explanation of the role.
  - Example: "This is a freelance AI Developer position. The role focuses on developing automation tools and working with machine learning models."

### Context Awareness:
- Keep track of the ongoing conversation to ensure responses are relevant.
- If you’re ever unsure of how to respond or need more context, provide a polite request for more information or clarification.

Remember, the conversation is not just about the candidate but also about maintaining a professional and positive interaction with the employer. Adapt your responses based on the tone of the conversation and maintain respect and professionalism at all times.

""".format(
    skills=parsed_resume['skills'],
    experience=parsed_resume['experience'],
    education=parsed_resume['education'],
    context="{context}",
    employer_response="{employer_response}"
)

class CallState:
    def __init__(self):
        self.conversations = {}
        self.recordings = {}
        # NEW: Add WebSocket tracking
        self.active_ws = {}

call_state = CallState()

# MODIFIED: Optimized AI response function
def get_ai_response(context, employer_response):
    """Get response from OpenAI with improved performance"""
    try:
        if employer_response is None:
            return None
            
        # NEW: Use shorter context to reduce tokens
        recent_context = context[-500:] if context else "Initial conversation"
        
        response = openai_client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Context: {recent_context}\nUser: {employer_response}"}
            ],
            max_tokens=50,
            temperature=0.7,
            presence_penalty=0.6  # NEW: Add presence penalty for more concise responses
        )
        
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error in get_ai_response: {str(e)}")
        return "I apologize for the technical difficulty. Would you like to know about the candidate's key qualifications?"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/call', methods=['POST'])
def initiate_call():
    """Initiate a call with recording"""
    try:
        phone_number = request.json['phone_number']
        
        call = twilio_client.calls.create(
            url=f"https://evident-orly-onewebonly-4acd77ba.koyeb.app/handle_call",
            to=phone_number,
            from_="+18452864551",
            record=True,
            recording_status_callback="https://evident-orly-onewebonly-4acd77ba.koyeb.app/recording-status"
        )
        
        call_state.conversations[call.sid] = {
            "context": "Initial call",
            "history": [],
            "transcription": ""
        }
        
        return jsonify({"status": "success", "call_sid": call.sid})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

# MODIFIED: Handle call with interrupt support
@app.route('/handle_call', methods=['POST'])
def handle_call():
    """Handle incoming call webhook with interrupt support"""
    call_sid = request.values.get('CallSid')
    stream_sid = request.values.get('StreamSid')
    employer_response = request.values.get('SpeechResult')
    
    response = VoiceResponse()
    
    # NEW: Handle interruption
    if employer_response and stream_sid in ws_connections:
        try:
            # Clear Twilio audio
            clear_message = {
                "streamSid": stream_sid,
                "event": "clear"
            }
            ws_connections[stream_sid].send(json.dumps(clear_message))
            
            # Cancel OpenAI response if active
            if stream_sid in call_state.active_ws:
                cancel_message = {"type": "response.cancel"}
                call_state.active_ws[stream_sid].send(json.dumps(cancel_message))
        except Exception as e:
            print(f"Interrupt error: {str(e)}")
    
    if not employer_response:
        initial_message = "Hello, this is James from HR Solutions. Is it a right time to talk?"
        response.say(initial_message, voice='Polly.Brian', bargein=True)
        
        call_state.conversations[call_sid] = {
            "context": "Initial call",
            "history": [{"ai": initial_message}],
            "transcription": f"James: {initial_message}\n"
        }
    else:
        conversation = call_state.conversations.get(call_sid, {
            "context": "Initial call",
            "history": [],
            "transcription": ""
        })
        
        conversation["transcription"] += f"Employer: {employer_response}\n"
        socketio.emit('transcription', {
            'speaker': 'Employer',
            'text': employer_response,
            'timestamp': datetime.now().isoformat()
        })
        
        # NEW: Use thread pool for AI response
        future = executor.submit(get_ai_response, conversation["context"], employer_response)
        ai_response = future.result(timeout=5)  # 5-second timeout
        
        if ai_response:
            response.say(ai_response, voice='Polly.Brian', bargein=True)
            conversation["history"].append({"employer": employer_response, "ai": ai_response})
            conversation["transcription"] += f"James: {ai_response}\n"
            conversation["context"] = f"Previous conversation: {json.dumps(conversation['history'][-3:])}"  # Keep only last 3 exchanges
            call_state.conversations[call_sid] = conversation
            socketio.emit('transcription', {
                'speaker': 'James',
                'text': ai_response,
                'timestamp': datetime.now().isoformat()
            })
    
    gather = Gather(input='speech', action='/handle_call', speechTimeout='auto')
    response.append(gather)
    
    return str(response)

# NEW: WebSocket connection handlers
@app.route('/ws-connect', methods=['POST'])
def ws_connect():
    stream_sid = request.json.get('stream_sid')
    ws_type = request.json.get('type')
    
    if stream_sid:
        ws_connections[stream_sid] = websockets.connect(
            f"wss://voice.twilio.com/v1/Streams/{stream_sid}"
        )
        if ws_type == 'openai':
            call_state.active_ws[stream_sid] = websockets.connect(
                "wss://api.openai.com/v1/audio/speech"
            )
    
    return jsonify({"status": "connected"})


@socketio.on_error_default
def default_error_handler(e):
    print(f'SocketIO error: {str(e)}')
    socketio.emit('error', {'message': 'An error occurred'}

                  
@app.route('/ws-disconnect', methods=['POST'])
def ws_disconnect():
    stream_sid = request.json.get('stream_sid')
    
    if stream_sid in ws_connections:
        ws_connections[stream_sid].close()
        del ws_connections[stream_sid]
    
    if stream_sid in call_state.active_ws:
        call_state.active_ws[stream_sid].close()
        del call_state.active_ws[stream_sid]
    
    return jsonify({"status": "disconnected"})

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

if __name__ == '__main__':
    socketio.run(app, 
                debug=True,
                host='0.0.0.0',
                port=5000,
                allow_unsafe_werkzeug=True)
