import os
import asyncio
import websockets
from fastapi import FastAPI, BackgroundTasks, WebSocket
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from twilio.rest import Client

# Load environment variables
load_dotenv()

# Twilio API credentials
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
PHONE_NUMBER_FROM = "+18452864551"  # Twilio Number
PHONE_NUMBER_TO = "+447823656762"  # User's Number

# OpenAI API Key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize Twilio client
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# FastAPI instance
app = FastAPI()


@app.get("/")
async def home():
    return {"message": "Twilio AI Voice Assistant Running!"}


@app.get("/start-call")
async def start_call(background_tasks: BackgroundTasks):
    """ Initiates a call with real-time AI conversation """
    try:
        # Start call with media stream enabled
        call = twilio_client.calls.create(
            to=PHONE_NUMBER_TO,
            from_=PHONE_NUMBER_FROM,
            twiml=f"""
                <Response>
                    <Start>
                        <Stream url="wss://evident-orly-onewebonly-4acd77ba.koyeb.app/media-stream" />
                    </Start>
                    <Say>Connecting you to our AI Assistant. Please start speaking.</Say>
                </Response>
            """,
        )

        background_tasks.add_task(log_call, call.sid)
        return JSONResponse(content={"message": "Call initiated!", "call_sid": call.sid}, status_code=200)

    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


async def log_call(call_sid: str):
    """ Log the call SID """
    print(f"📞 Call started with SID: {call_sid}")


@app.websocket("/media-stream")
async def media_stream(websocket: WebSocket):
    """ Handles real-time audio streaming between Twilio and OpenAI """

    await websocket.accept()
    print("🔄 Connection Opened")

    try:
        async with websockets.connect(
            "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01",
            extra_headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "OpenAI-Beta": "realtime=v1"}
        ) as openai_ws:

            while True:
                # Receive audio from Twilio
                audio_data = await websocket.receive_bytes()

                if not audio_data:
                    break  # Stop if no audio is received

                # Send user audio to OpenAI
                await openai_ws.send(audio_data)

                # Get AI response
                ai_audio_response = await openai_ws.recv()

                # Send AI response back to Twilio
                await websocket.send_bytes(ai_audio_response)

    except Exception as e:
        print(f"❌ Error: {str(e)}")

    finally:
        print("🔴 Connection Closed")
        await websocket.close()
