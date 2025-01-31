import os
from fastapi import FastAPI, BackgroundTasks
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse
import openai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize Twilio and OpenAI clients
openai.api_key = os.getenv("OPENAI_API_KEY")
twilio_client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))

app = FastAPI()

# Call details
CALLER_ID = os.getenv("PHONE_NUMBER_FROM")  # Your Twilio phone number
TARGET_PHONE = "+447823656762"  # The target phone number
CALLER_NAME = "Social Media Marketing Expert"

@app.get("/start-call")
async def start_call(background_tasks: BackgroundTasks):
    """Start a marketing call via Twilio."""
    background_tasks.add_task(make_call)
    return {"message": "Call is being initiated!"}

def make_call():
    """Initiate a call and connect it with a Twilio Stream."""
    # Create the call using Twilio's REST API
    call = twilio_client.calls.create(
        to=TARGET_PHONE,
        from_=CALLER_ID,
        url="http://demo.twilio.com/docs/voice.xml"  # Twilio will request this URL to play the first response
    )
    print(f"Call initiated: SID {call.sid}")

@app.post("/twilio-webhook")
async def twilio_webhook(data: dict):
    """Handle the Twilio response to the call."""
    response = VoiceResponse()

    # AI-generated marketing message
    prompt = (
        "You are a social media marketing expert calling a business. "
        "Introduce yourself as a professional offering social media marketing services. "
        "Talk about the importance of online presence, branding, and how you can help them grow their business."
    )

    # Get response from OpenAI (AI-based sales script)
    try:
        ai_response = openai.Completion.create(
            model="text-davinci-003",  # Or another model you prefer
            prompt=prompt,
            max_tokens=150,
            temperature=0.7
        )
        message = ai_response.choices[0].text.strip()
        print(f"AI message: {message}")

        # Add the AI response as a speech prompt
        response.say(message, voice="alice")

    except Exception as e:
        print(f"Error generating AI response: {e}")
        response.say("Sorry, I couldn't generate a message at this time.", voice="alice")

    return str(response)

