import os
from flask import Flask, request, jsonify
from twilio.rest import Client as TwilioClient
from twilio.twiml.voice_response import VoiceResponse, Gather
from openai import OpenAI

app = Flask(__name__)

class AICallSystem:
    def __init__(self):
        # Initialize API clients
        self.twilio_client = TwilioClient(
            os.getenv('TWILIO_ACCOUNT_SID'),
            os.getenv('TWILIO_AUTH_TOKEN')
        )
        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.twilio_number = os.getenv('TWILIO_PHONE_NUMBER')
        
        # Store conversation history
        self.conversations = {}
        
        # System prompt for consistent AI behavior
        self.SYSTEM_PROMPT = """You are a helpful AI assistant conducting a phone conversation. 
        Keep responses brief and natural, under 15 seconds of speaking time. Be concise and direct."""

    def generate_ai_response(self, user_input, call_sid):
        """Generate AI response using OpenAI"""
        # Get conversation history or initialize new one
        conversation = self.conversations.get(call_sid, [])
        
        # Add user input to conversation
        conversation.append({"role": "user", "content": user_input})
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    *conversation
                ],
                max_tokens=50  # Keep responses brief
            )
            ai_response = response.choices[0].message.content
            
            # Store conversation
            conversation.append({"role": "assistant", "content": ai_response})
            self.conversations[call_sid] = conversation
            
            return ai_response
        except Exception as e:
            print(f"Error generating AI response: {e}")
            return "I apologize, could you please repeat that?"

    def initiate_call(self, to_number):
        """Initiate Twilio call"""
        try:
            call = self.twilio_client.calls.create(
                to=to_number,
                from_=self.twilio_number,
                url=os.getenv('TWILIO_WEBHOOK_URL')
            )
            return call.sid
        except Exception as e:
            print(f"Error initiating call: {e}")
            return None

# Initialize the AI system
ai_system = AICallSystem()

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming Twilio webhook requests"""
    response = VoiceResponse()
    
    # Get call SID for tracking conversation
    call_sid = request.values.get('CallSid')
    
    # Get user input if any
    user_input = request.values.get('SpeechResult')
    
    if user_input:
        # Generate AI response
        ai_response = ai_system.generate_ai_response(user_input, call_sid)
        
        # Add the response to TwiML
        gather = Gather(
            input='speech',
            action='/webhook',
            method='POST',
            speech_timeout='auto',
            interrupt='true'  # Allow barge-in/interruption
        )
        gather.say(ai_response)
        response.append(gather)
    else:
        # Initial greeting
        gather = Gather(
            input='speech',
            action='/webhook',
            method='POST',
            speech_timeout='auto',
            interrupt='true'  # Allow barge-in/interruption
        )
        gather.say("Hello! How can I help you today?")
        response.append(gather)
    
    # Add a fallback gather in case no input is received
    response.redirect('/webhook')
    
    return str(response)

@app.route('/call', methods=['POST'])
def make_call():
    """Endpoint to initiate a call"""
    phone_number = request.json.get('phone_number')
    if not phone_number:
        return jsonify({"status": "error", "message": "Phone number is required"}), 400
    
    call_sid = ai_system.initiate_call(phone_number)
    if call_sid:
        return jsonify({"status": "success", "call_sid": call_sid})
    return jsonify({"status": "error", "message": "Failed to initiate call"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
