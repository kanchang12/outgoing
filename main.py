import os
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from twilio.rest import Client as TwilioClient
from openai import OpenAI
from elevenlabs import voices, save, stream

app = Flask(__name__)
socketio = SocketIO(app)

class AICallSystem:
    def __init__(self):
        # API Clients
        self.twilio_client = TwilioClient(
            os.getenv('TWILIO_ACCOUNT_SID'), 
            os.getenv('TWILIO_AUTH_TOKEN')
        )
        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Configuration
        self.twilio_number = os.getenv('TWILIO_PHONE_NUMBER')
        self.elevenlabs_voice = voices()[0].voice_id  # Use first available voice

        # System prompt for consistent AI behavior
        self.SYSTEM_PROMPT = """You are a helpful AI assistant conducting a phone conversation. 
        Respond naturally and concisely as if you're speaking on a phone call."""

    def generate_ai_response(self, user_input):
        """Generate AI response using OpenAI"""
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": f"Respond briefly to: {user_input}"}
                ],
                max_tokens=50
            )
            return response.choices[0].message.content
        except Exception as e:
            return "I apologize, could you please repeat that."

    def text_to_speech(self, text):
        """Convert text to speech using ElevenLabs"""
        audio = stream(
            text=text,
            voice=self.elevenlabs_voice
        )
        # Save audio locally
        with open("response.mp3", "wb") as f:
            f.write(audio.read())
        return "response.mp3"

    def initiate_call(self, to_number):
        """Initiate Twilio call"""
        call = self.twilio_client.calls.create(
            to=to_number,
            from_=self.twilio_number,
            url='YOUR_TWILIO_WEBHOOK_URL'  # TwiML endpoint
        )
        return call.sid

ai_system = AICallSystem()

@app.route('/')
def index():
    return render_template('call_interface.html')

@app.route('/make_call', methods=['POST'])
def make_call():
    phone_number = request.json.get('phone_number')
    call_sid = ai_system.initiate_call(phone_number)
    return jsonify({"status": "success", "call_sid": call_sid})

@socketio.on('user_input')
def handle_user_input(data):
    user_input = data['message']
    ai_response = ai_system.generate_ai_response(user_input)
    ai_speech_file = ai_system.text_to_speech(ai_response)
    emit('ai_response', {
        'text': ai_response,
        'audio_file': ai_speech_file
    })

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))
