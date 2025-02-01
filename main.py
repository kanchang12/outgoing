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

def should_end_call(user_input):
    """Check if user's input indicates they want to end the call"""
    ending_phrases = [
        'thank you', 'thanks', 'bye', 'goodbye', 'take care', 
        'see you', 'good bye', 'have a good day', 'end call'
    ]
    return any(phrase in user_input.lower() for phrase in ending_phrases)

def generate_response(user_input):
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": """You are James, a professional social media marketing consultant with 8 years of experience. Your expertise includes:
- Instagram and TikTok growth strategies
- Content planning and creation
- Brand building on social media
- Lead generation through social platforms
- Social media advertising

Communication style:
- Friendly and professional
- Use concrete examples and success stories
- Focus on ROI and business benefits
- Ask questions about their business to provide tailored advice
- Keep responses concise (under 15 seconds)
- Naturally guide the conversation towards a potential consultation

If asked about pricing: Suggest scheduling a free consultation to create a customized plan based on their specific needs.

Remember: You're having a natural conversation while showcasing your expertise in social media marketing
Keep responses under 15 seconds."""},
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
    
    if user_input:
        # Check if user wants to end call
        if should_end_call(user_input):
            response.say("Thank you for calling. Goodbye!")
            response.hangup()
            return str(response)
    
        # Generate and speak AI response
        ai_response = generate_response(user_input)
        gather = Gather(
            input='speech',
            action='/webhook',
            method='POST',
            speech_timeout='auto',
            interrupt='true'
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
            interrupt='true'
        )
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
