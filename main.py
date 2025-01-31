from flask import Flask, render_template, request, jsonify
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Gather, Say
from openai import OpenAI
from flask_socketio import SocketIO
import PyPDF2
import re
import json
from datetime import datetime
import os

app = Flask(__name__)
socketio = SocketIO(app)

# Initialize clients
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
twilio_client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF file"""
    with open(pdf_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
    return text

def parse_resume(pdf_text):
    """Parse relevant information from PDF text"""
    experience = re.findall(r'Experience(.*?)Education', pdf_text, re.DOTALL)
    skills = re.findall(r'Top Skills(.*?)Languages', pdf_text, re.DOTALL)
    education = re.findall(r'Education(.*?)$', pdf_text, re.DOTALL)
    
    return {
        'experience': experience[0] if experience else '',
        'skills': skills[0] if skills else '',
        'education': education[0] if education else ''
    }

# Read and parse PDF at startup
# Direct path to PDF (assuming it's in the same folder as main.py)
PDF_PATH = "Profile.pdf"

# Extract text from the PDF
pdf_text = extract_text_from_pdf(PDF_PATH)

# Parse the resume content
parsed_resume = parse_resume(pdf_text)

SYSTEM_PROMPT = f"""
You are James, a professional HR consultant discussing a candidate for an AI Developer (Freelance) position. 
The candidate's profile:

Key Skills:
{parsed_resume['skills']}

Relevant Experience:
{parsed_resume['experience']}

Education:
{parsed_resume['education']}

Core Personality Traits:
- Professional and articulate
- Knowledgeable about AI development and technical roles
- Enthusiastic about the candidate's qualifications
- Attentive to the employer's needs

Focus on highlighting:
1. AI and automation experience
2. Python development skills
3. Chatbot development expertise
4. Freelance project experience
5. Technical writing abilities

Current conversation context: {{context}}
Previous employer response: {{employer_response}}

Respond naturally as an HR consultant would in a phone conversation.
"""

class CallState:
    def __init__(self):
        self.conversations = {}
        self.recordings = {}

call_state = CallState()

@app.route('/')
def index():
    return render_template('index.html')

def get_ai_response(context, employer_response):
    """Get response from OpenAI"""
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT.format(
                    context=context,
                    employer_response=employer_response
                )},
                {"role": "user", "content": employer_response}
            ],
            max_tokens=250,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error getting AI response: {e}")
        return "I apologize, but I'm having trouble with my connection. Let me get back to you at a better time."

@app.route('/call', methods=['POST'])
def initiate_call():
    """Initiate a call with recording"""
    try:
        phone_number = request.json['phone_number']
        initial_message = (
            "Hello, this is James from HR Solutions. This call is being recorded for quality purposes. "
            "I'm reaching out regarding an experienced AI Developer candidate for your freelance position. "
            "Would you have a moment to discuss their qualifications?"
        )
        
        call = twilio_client.calls.create(
            url="https://evident-orly-onewebonly-4acd77ba.koyeb.app/handle_call",  # Your Koyeb URL
            to=phone_number,
            from_="+18452864551",
            record=True,
            recording_status_callback=f"https://evident-orly-onewebonly-4acd77ba.koyeb.app/recording-status"
        )
        
        call_state.conversations[call.sid] = {
            "context": "Initial call",
            "history": [{"ai": initial_message}],
            "transcription": ""
        }
        
        return jsonify({"status": "success", "call_sid": call.sid})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/handle_call', methods=['POST'])
def handle_call():
    """Handle incoming call webhook"""
    call_sid = request.values.get('CallSid')
    employer_response = request.values.get('SpeechResult')
    
    if employer_response:
        socketio.emit('transcription', {
            'speaker': 'Employer',
            'text': employer_response,
            'timestamp': datetime.now().isoformat()
        })
        
        if call_sid in call_state.conversations:
            call_state.conversations[call_sid]["transcription"] += f"Employer: {employer_response}\n"
    
    conversation = call_state.conversations.get(call_sid, {
        "context": "Initial call",
        "history": [],
        "transcription": ""
    })
    
    ai_response = get_ai_response(conversation["context"], employer_response)
    
    socketio.emit('transcription', {
        'speaker': 'James',
        'text': ai_response,
        'timestamp': datetime.now().isoformat()
    })
    
    conversation["history"].append({
        "employer": employer_response,
        "ai": ai_response
    })
    conversation["context"] = f"Previous conversation: {json.dumps(conversation['history'])}"
    conversation["transcription"] += f"James: {ai_response}\n"
    call_state.conversations[call_sid] = conversation
    
    response = VoiceResponse()
    response.say(ai_response, voice='Polly.Brian')
    
    gather = Gather(input='speech', timeout=3, action='/handle_call')
    response.append(gather)
    
    return str(response)

@app.route('/end-call', methods=['POST'])
def end_call():
    """End the call and save recording"""
    try:
        call_sid = request.json['call_sid']
        call = twilio_client.calls(call_sid).update(status="completed")
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/download-transcript/<call_sid>')
def download_transcript(call_sid):
    """Download call transcript"""
    if call_sid in call_state.conversations:
        transcript = call_state.conversations[call_sid]["transcription"]
        return jsonify({
            "status": "success",
            "transcript": transcript
        })
    return jsonify({
        "status": "error",
        "message": "Transcript not found"
    })

if __name__ == '__main__':
    socketio.run(app, debug=True)
