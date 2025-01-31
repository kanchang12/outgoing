import os
from flask import Flask, request, jsonify
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Gather
from openai import OpenAI

app = Flask(__name__)

# Initialize clients
twilio_client = Client(
    os.getenv('TWILIO_ACCOUNT_SID'),
    os.getenv('TWILIO_AUTH_TOKEN')
)
openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def generate_response(user_input):
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful phone assistant. Keep responses under 15 seconds."},
                {"role": "user", "content": user_input}
            ],
            max_tokens=50
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"OpenAI Error: {e}")
        return "I apologize, I didn't catch that. Could you please repeat?"

@app.route("/webhook", methods=['POST'])
def webhook():
    response = VoiceResponse()
    
    # Get user's speech input if any
    user_input = request.values.get('SpeechResult')
    
    # Create a Gather object to collect user speech
    gather = Gather(
        input='speech',
        action='/webhook',
        method='POST',
        speech_timeout='auto',
        interrupt='true'
    )
    
    if user_input:
        # Generate and speak AI response
        ai_response = generate_response(user_input)
        gather.say(ai_response)
    else:
        # Initial greeting
        gather.say("Hello! How can I help you today?")
    
    response.append(gather)
    
    # Add a redirect to handle no input
    response.redirect('/webhook')
    
    return str(response)

@app.route("/call", methods=['POST'])
def make_call():
    try:
        phone_number = request.json.get('phone_number')
        if not phone_number:
            return jsonify({"error": "Phone number is required"}), 400
        
        # Make the call
        call = twilio_client.calls.create(
            to=phone_number,
            from_=os.getenv('TWILIO_PHONE_NUMBER'),
            url="https://evident-orly-onewebonly-4acd77ba.koyeb.app/webhook"
        )
        
        return jsonify({"success": True, "call_sid": call.sid})
    except Exception as e:
        print(f"Call Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
