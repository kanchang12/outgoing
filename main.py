import os
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from twilio.rest import Client as TwilioClient
from openai import OpenAI
from elevenlabs import Voice, generate, stream

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
        
        # Get default voice ID - using Voice.from_api() to get available voices
        try:
            self.elevenlabs_voice = Voice.from_api()[0].voice_id
        except Exception as e:
            print(f"Warning: Could not fetch ElevenLabs voice: {e}")
            self.elevenlabs_voice = "default"  # Use a default voice ID or handle this case appropriately
            
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
            print(f"Error generating AI response: {e}")
            return "I apologize, could you please repeat that."

    def text_to_speech(self, text):
        """Convert text to speech using ElevenLabs"""
        try:
            audio = generate(
                text=text,
                voice=self.elevenlabs_voice,
                stream=True
            )
            
            # Save audio locally
            filename = "response.mp3"
            with open(filename, "wb") as f:
                for chunk in audio:
                    f.write(chunk)
            return filename
        except Exception as e:
            print(f"Error generating speech: {e}")
            return None

    def initiate_call(self, to_number):
        """Initiate Twilio call"""
        try:
            call = self.twilio_client.calls.create(
                to=to_number,
                from_=self.twilio_number,
                url='YOUR_TWILIO_WEBHOOK_URL'  # TwiML endpoint
            )
            return call.sid
        except Exception as e:
            print(f"Error initiating call: {e}")
            return None

@app.route('/')
def index():
    return render_template('call_interface.html')

@app.route('/make_call', methods=['POST'])
def make_call():
    phone_number = request.json.get('phone_number')
    if not phone_number:
        return jsonify({"status": "error", "message": "Phone number is required"}), 400
    
    call_sid = ai_system.initiate_call(phone_number)
    if call_sid:
        return jsonify({"status": "success", "call_sid": call_sid})
    return jsonify({"status": "error", "message": "Failed to initiate call"}), 500

@socketio.on('user_input')
def handle_user_input(data):
    user_input = data.get('message')
    if not user_input:
        emit('ai_response', {
            'text': "No input received",
            'audio_file': None
        })
        return
    
    ai_response = ai_system.generate_ai_response(user_input)
    ai_speech_file = ai_system.text_to_speech(ai_response)
    
    emit('ai_response', {
        'text': ai_response,
        'audio_file': ai_speech_file
    })

if __name__ == '__main__':
    ai_system = AICallSystem()
    port = int(os.environ.get('PORT', 8000))
    socketio.run(app, host='0.0.0.0', port=port)
