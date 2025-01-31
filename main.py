import os
import json
import asyncio
from flask import Flask, request, jsonify
from flask_socketio import SocketIO
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Gather
from openai import OpenAI
from dotenv import load_dotenv
import websockets

load_dotenv()

# Configuration
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize clients
twilio_client = Client(
    os.getenv('TWILIO_ACCOUNT_SID'), 
    os.getenv('TWILIO_AUTH_TOKEN')
)
openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Constants
SYSTEM_PROMPT = """You are James, a professional HR consultant conducting a phone conversation about a candidate for an AI Developer position."""

@app.route('/start-call', methods=['POST', 'GET'])
def start_call_webhook():
    """Handle incoming Twilio call webhook"""
    response = VoiceResponse()
    
    # Initial greeting
    response.say("Hello, this is James from HR Solutions", voice='Polly.Brian')
    
    # Gather for speech input
    gather = Gather(input='speech', action='/process-response', speechTimeout='auto')
    response.append(gather)
    
    return str(response)

@app.route('/process-response', methods=['POST'])
def process_response():
    """Process employer's speech response"""
    employer_response = request.values.get('SpeechResult', '')
    
    try:
        # Use OpenAI to generate AI response
        ai_response = openai_client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": employer_response}
            ]
        ).choices[0].message.content
    except Exception as e:
        ai_response = "I'm experiencing technical difficulties. Could you please repeat that?"
    
    # Create Twilio response
    response = VoiceResponse()
    response.say(ai_response, voice='Polly.Brian')
    
    # Set up next gather for continued conversation
    gather = Gather(input='speech', action='/process-response', speechTimeout='auto')
    response.append(gather)
    
    return str(response)

@app.route('/initiate_call', methods=['POST'])
def initiate_call():
    """Initiate a Twilio call"""
    try:
        phone_number = request.json.get('phone_number', '+447823656762')
        
        # Ensure phone number is in the correct format
        if not phone_number.startswith('+'):
            phone_number = f'+{phone_number}'
        
        call = twilio_client.calls.create(
            url="https://evident-orly-onewebonly-4acd77ba.koyeb.app/start-call",
            to=phone_number,
            from_="+18452864551",
            record=True
        )
        
        return jsonify({
            "status": "success", 
            "call_sid": call.sid,
            "phone_number": phone_number
        })
    
    except Exception as e:
        return jsonify({
            "status": "error", 
            "message": str(e)
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
