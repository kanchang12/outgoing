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
SYSTEM_PROMPT = """

System Prompt: Social Media Marketing Support
You are a Social Media Marketing Expert providing quick, relevant guidance for a client’s business. Your goal is to engage with the client professionally, offering social media marketing strategies, content tips, and advertising suggestions.

Key Areas to Address:

Platform Recommendations – Suggest the best social media platforms based on the client's business type.
Content Strategy – Offer tips on creating engaging posts, visuals, and messaging.
Advertising Ideas – Advise on paid campaigns to boost reach and engagement.
Analytics – Provide insights on measuring success through social media metrics.
Approach:

Professional and Friendly: Start with a welcoming tone and ask about their business goals.
Actionable Suggestions: Focus on providing simple, clear steps.
Example Response if the Client Says "Hi":
"Hello! Thanks for reaching out. I'd love to help you grow your business on social media. Could you tell me a bit about your business and your goals? That way, I can recommend the best platforms and strategies for you."

"""

@app.route('/start-call', methods=['POST', 'GET'])
def start_call_webhook():
    """Handle incoming Twilio call webhook"""
    response = VoiceResponse()
    
    # Initial greeting
    response.say("Hello, this is James How are you today?", voice='Polly.Brian-Neural')
    
    # Gather for speech input
    gather = Gather(input='speech', action='/process-response', speechTimeout='auto')
    response.append(gather)
    
    return str(response)

@app.route('/process-response', methods=['POST'])
def process_response():
    """Process employer's speech response with interruption handling"""
    employer_response = request.values.get('SpeechResult', '').lower()
    
    # Explicit interruption keywords
    stop_keywords = ['stop', 'pause', 'quiet', 'enough', 'wait']
    
    # Check for interruption
    if any(keyword in employer_response for keyword in stop_keywords):
        response = VoiceResponse()
        response.say("I apologize. I'll pause and listen.", voice='Polly.Brian')
        gather = Gather(input='speech', action='/process-response', speechTimeout='auto')
        response.append(gather)
        return str(response)
    
    try:
        ai_response = openai_client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Respond briefly to: {employer_response}"}
            ],
            max_tokens=50  # Limit response length
        ).choices[0].message.content
    except Exception as e:
        ai_response = "I apologize, could you please repeat that?"
    
    response = VoiceResponse()
    response.say(ai_response, voice='Polly.Brian')
    
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
