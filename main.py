import os
from fastapi import FastAPI, WebSocket
import websockets
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse
from fastapi.responses import HTMLResponse

# Define your Twilio and OpenAI credentials
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
PHONE_NUMBER_FROM = os.getenv('PHONE_NUMBER_FROM')
PHONE_NUMBER_TO = os.getenv('PHONE_NUMBER_TO')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

app = FastAPI()

# Define the AI assistant's persona
AI_PERSONA_PROMPT = """
You are an enthusiastic sales agent specializing in social media marketing.
Your goal is to convince the customer to sign up for our services.
Be confident, engaging, and persuasive, but not pushy.
Address objections with smart counters.
Keep responses short, natural, and conversational.
Always end with a strong call to action.
"""

@app.post("/start-call")
async def start_call():
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

    # Place the call to the user
    call = client.calls.create(
        to=PHONE_NUMBER_TO,
        from_=PHONE_NUMBER_FROM,
        url="http://your-server-url.com/handle-call"  # Replace with your actual endpoint
    )

    return {"message": "Call initiated", "sid": call.sid}

@app.websocket("/media-stream")
async def media_stream(websocket: WebSocket):
    """ Handles real-time AI conversation with Twilio """

    await websocket.accept()
    print("🔄 Connection Opened")

    try:
        async with websockets.connect(
            "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01",
            extra_headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "OpenAI-Beta": "realtime=v1"}
        ) as openai_ws:

            # Send the persona prompt first
            await openai_ws.send(AI_PERSONA_PROMPT)

            while True:
                # Receive user speech from Twilio
                audio_data = await websocket.receive_bytes()

                if not audio_data:
                    break  # Stop if no audio is received

                # Send user audio to OpenAI
                await openai_ws.send(audio_data)

                # Get AI-generated response
                ai_audio_response = await openai_ws.recv()

                # Send AI response back to Twilio
                await websocket.send_bytes(ai_audio_response)

    except Exception as e:
        print(f"❌ Error: {str(e)}")

    finally:
        print("🔴 Connection Closed")
        await websocket.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
