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

# Initialize Flask and SocketIO with proper configuration
app = Flask(__name__)
Payload.max_decode_packets = 50
socketio = SocketIO(app, 
                   cors_allowed_origins="*",
                   ping_timeout=60,
                   ping_interval=25)

# Initialize clients
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
twilio_client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))

def clean_text(text):
    """Clean extracted text from PDF"""
    # Remove page markers
    text = re.sub(r'\xa0 Page \d+ of \d+\xa0 \xa0', '', text)
    # Remove URLs
    text = re.sub(r'https?://\S+', '', text)
    # Remove extra whitespace
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
    # Improved regex patterns
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

# Updated system prompt
SYSTEM_PROMPT = """
You are James, a professional HR consultant discussing an AI Developer candidate. 
Keep responses under 15 words unless asked for details.
Be direct and concise.
Pause for employer responses.

Candidate Skills: {skills}
Recent Experience: {experience}

Current context: {context}
Employer response: {employer_response}
"""

class CallState:
    def __init__(self):
        self.conversations = {}
        self.recordings = {}

call_state = CallState()

def get_ai_response(context, employer_response):
    try:
        formatted_prompt = SYSTEM_PROMPT.format(
            skills=parsed_resume['skills'],
            experience=parsed_resume['experience'][:100],  # Limit length
            context=context,
            employer_response=employer_response
        )
        
        response = openai_client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": formatted_prompt},
                {"role": "user", "content": employer_response}
            ],
            max_tokens=50,  # Reduced tokens for shorter responses
            temperature=0.7
        )
        
        return response.choices[0].message.content
    except Exception as e:
        return "Would you like to know about their AI development experience?"

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
        
        # Initialize conversation state
        call_state.conversations[call.sid] = {
            "context": "Initial call",
            "history": [],
            "transcription": ""
        }
        
        return jsonify({"status": "success", "call_sid": call.sid})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/handle_call', methods=['POST'])
def handle_call():
    call_sid = request.values.get('CallSid')
    employer_response = request.values.get('SpeechResult')
    
    response = VoiceResponse()
    
    if not employer_response:
        initial_message = "Hi, James here about an AI Developer position. Got a minute to discuss?"
        response.say(initial_message, voice='Polly.Brian')
        
        if call_sid not in call_state.conversations:
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
        
        # Set shorter timeout and bargein=True to allow interruption
        gather = Gather(input='speech', timeout=1, action='/handle_call', bargein=True)
        response.append(gather)

        ai_response = get_ai_response(conversation["context"], employer_response)
        if ai_response:
            response.say(ai_response, voice='Polly.Brian', bargein=True)
            
            conversation["history"].append({
                "employer": employer_response,
                "ai": ai_response
            })
            conversation["transcription"] += f"James: {ai_response}\n"
            call_state.conversations[call_sid] = conversation

    return str(response)

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
