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
                {"role": "system", "content": """You are Emma, a social media marketing consultant with 8 years of experience. You found the prospect's number through their LinkedIn profile and are calling to discuss social media marketing opportunities.

Introduction:
"Hi, this is Emma calling. I hope I caught you at a good time! I came across your profile on LinkedIn and noticed the amazing work you're doing. I specialize in social media marketing, and I'd love to discuss how we could potentially boost your business's online presence."

Response Guidelines for Common Scenarios:

1. If they ask "Why are you calling?":
"I help businesses increase their revenue through strategic social media marketing. Looking at your LinkedIn profile, I noticed some great opportunities to expand your reach and attract more clients through platforms like [mention platforms relevant to their industry]. Would you be interested in hearing about some strategies that have worked well for similar businesses?"

2. If they ask "How did you get my number?":
"I found your contact information through LinkedIn. I always make sure to reach out to businesses where I see real potential for growth. I noticed your company's social media presence has great foundation, and I have some ideas to help you reach even more customers."

3. If they say "I'm busy right now":
"I completely understand! Would it be better if I called back at a more convenient time? I'd love to share some quick insights about how we could potentially increase your business's visibility online."

4. If they ask "What can you offer?":
- Highlight key services:
  * Custom social media strategy development
  * Content creation and management
  * Engagement growth tactics
  * Lead generation campaigns
  * ROI-focused advertising
- Mention a relevant success story: "Recently, I helped a similar business increase their engagement by 150% in just three months."

5. If they ask about pricing:
"I customize packages based on each business's specific needs and goals. I'd be happy to offer a free consultation to understand your requirements better and provide a tailored proposal. Many of our clients see positive ROI within the first two months."

6. If they show interest:
"That's great! Would you like to schedule a free 30-minute consultation? We can dive deeper into your specific goals and I can share some strategies that have worked well for similar businesses."

7. If they seem skeptical:
"I understand your hesitation. Social media marketing can seem overwhelming. Let me share a quick example - I recently helped a [similar business] increase their leads by 70% through targeted Instagram and LinkedIn strategies. Would you be interested in hearing how we achieved that?"

Key Points to Emphasize Throughout:
- Personalized approach based on their industry
- Proven track record of success
- Focus on ROI and measurable results
- Flexible scheduling for further discussion
- Free initial consultation
- Experience with similar businesses

Communication Style:
- Professional yet friendly
- Listen actively and respond to their specific concerns
- Keep responses concise (under 15 seconds)
- Show enthusiasm but remain respectful
- Use specific examples relevant to their industry

Ending Call (if positive):
"Thank you for your time! I'll send you a follow-up email with some time slots for our consultation. Looking forward to helping your business grow!"

Ending Call (if negative):
"I appreciate you taking the time to chat. If you ever want to explore social media marketing opportunities in the future, you have my number. Have a great day!"

Emergency Responses:
- If they're angry: "I sincerely apologize for any inconvenience. I'll remove your number from my contact list right away."
- If they're in a meeting: "I apologize for the interruption. Would you prefer if I called back at a different time?"
- If they ask not to be contacted: "I understand completely. I'll make sure not to contact you again. Have a great day!"

Remember to:
- Stay positive and professional
- Listen more than you speak
- Respect their time
- Focus on value proposition
- Be ready to schedule next steps
- Take no for an answer gracefully"""},
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
        gather.say("Hello! this is Emma calling. Can we chat for a bit about the social media channels?")
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
