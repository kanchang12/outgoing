import os
import json
import base64
import asyncio
import re
from flask import Flask, request, jsonify
from flask_socketio import SocketIO
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Gather, Say
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
PHONE_NUMBER_FROM = os.getenv('PHONE_NUMBER_FROM')
SYSTEM_PROMPT = """You are James, a professional HR consultant conducting a phone conversation about a candidate for an AI Developer position."""

class MediaStreamHandler:
    def __init__(self):
        self.openai_ws = None
        self.stream_sid = None

    async def connect_to_openai(self):
        """Establish WebSocket connection with OpenAI Realtime API"""
        try:
            self.openai_ws = await websockets.connect(
                'wss://api.openai.com/v1/realtime',
                extra_headers={
                    "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
                    "OpenAI-Beta": "realtime=v1"
                }
            )
            return self.openai_ws
        except Exception as e:
            print(f"OpenAI WebSocket connection error: {e}")
            return None

    async def handle_media_stream(self, websocket):
        """Process media stream from Twilio to OpenAI"""
        try:
            async for message in websocket:
                data = json.loads(message)
                
                if data['event'] == 'media' and self.openai_ws:
                    # Send audio to OpenAI
                    audio_append = {
                        "type": "input_audio_buffer.append",
                        "audio": data['media']['payload']
                    }
                    await self.openai_ws.send(json.dumps(audio_append))
                
                elif data['event'] == 'start':
                    self.stream_sid = data['start']['streamSid']
                    print(f"Stream started: {self.stream_sid}")
        
        except Exception as e:
            print(f"Media stream handling error: {e}")

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
    employer_response = request.values.get('SpeechResult')
    
    # Use OpenAI to generate AI response
    ai_response = openai_client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": employer_response}
        ]
    ).choices[0].message.content
    
    # Create Twilio response
    response = VoiceResponse()
    response.say(ai_response, voice='Polly.Brian')
    
    # Set up next gather for continued conversation
    gather = Gather(input='speech', action='/process-response', speechTimeout='auto')
    response.append(gather)
    
    return str(response)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
