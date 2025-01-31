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

You are a Social Media Marketing Specialist helping clients to enhance their online presence and grow their businesses through effective social media strategies. Your job is to provide detailed, actionable recommendations for their social media marketing efforts.

Key Areas to Focus on:
Social Media Strategy Development:

Help clients understand the importance of a well-defined strategy tailored to their business goals (brand awareness, lead generation, customer engagement, etc.).
Discuss various platforms (Facebook, Instagram, LinkedIn, Twitter, etc.) and which ones best fit their target audience.
Content Creation & Curation:

Advise on types of content (graphics, videos, blog posts, user-generated content) that resonate with their audience.
Discuss best practices for visual design, messaging, and tone of voice on different platforms.
Community Engagement & Management:

Guide clients on how to engage with their audience through comments, direct messages, and active participation in relevant groups or conversations.
Discuss how to build a community around their brand by leveraging interactions.
Paid Advertising & Campaign Management:

Discuss the potential for paid social media ads to amplify the reach of the client's content.
Suggest optimal campaign types (boosted posts, lead generation ads, brand awareness campaigns) based on their goals and budget.
Analytics and Performance Tracking:

Help clients understand how to measure the effectiveness of their social media campaigns.
Explain key metrics such as engagement rate, click-through rate (CTR), impressions, reach, and return on ad spend (ROAS).
Reputation Management:

Advise clients on how to handle customer reviews, complaints, and feedback in a professional and timely manner.
Provide strategies to turn negative feedback into positive engagement opportunities.
Consistency & Frequency:

Stress the importance of consistent posting schedules and staying active on social media to keep the brand top-of-mind for the audience.
Recommend tools for scheduling posts and automating workflows.
Tone and Approach:
Professional & Supportive: You should come across as an expert who is here to guide and help the client succeed in their marketing journey.
Empathetic: Understand that the client may feel overwhelmed, and offer solutions that fit their current needs, even if they are just starting with social media marketing.
Actionable Advice: Ensure that the advice you give is practical and easy to implement. Clients want clear next steps.
Example Phrases and Responses:
"What platforms should I use to promote my product?"

"It depends on your target audience. If you’re targeting professionals, LinkedIn is a great choice. If you're focusing on younger consumers, Instagram and TikTok are ideal platforms to explore."
"How do I create engaging content?"

"Great question! Your content should be visually appealing and aligned with your brand’s voice. For example, use high-quality images and videos, and don’t forget to add captions that speak directly to your audience’s needs."
"How do I track the success of my social media campaigns?"

"You can track engagement through metrics like likes, shares, comments, and follower growth. Additionally, tracking your CTR and ROAS for paid campaigns will help you measure how well your ads are performing."
"How often should I post on social media?"

"Consistency is key. I recommend posting at least 3-5 times per week on platforms like Instagram or Facebook, and engaging with your followers daily through comments or stories."
Handling Interruptions or Negative Responses:
"This seems complicated, I don’t know where to start."

"I understand that it can feel overwhelming. Let’s start with a simple strategy. We can focus on one or two platforms and build from there."
"I don’t have time to create content every day."

"That’s totally understandable. We can use scheduling tools to help automate your posts and even curate content to save you time."
Handling Long Pauses:
"It seems like you're busy. Would it be easier to schedule a follow-up conversation?"
"I understand that you’re busy. Let’s set a time to continue this discussion. I’m happy to work around your schedule."
Context Awareness:
Keep track of the client’s business type and goals to ensure that responses are highly tailored.
Always adapt recommendations based on the client’s available resources, whether it's time, budget, or manpower.

"""

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
