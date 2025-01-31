import os
import json
import asyncio
import base64
import websockets
from fastapi import FastAPI, WebSocket
from fastapi.responses import JSONResponse
from twilio.rest import Client
from dotenv import load_dotenv
import uvicorn

# Load environment variables
load_dotenv()

# Twilio API credentials
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
PHONE_NUMBER_FROM = os.getenv("PHONE_NUMBER_FROM")  # Your Twilio phone number
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Twilio & OpenAI Clients
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# FastAPI app instance
app = FastAPI()

# Twilio Call Config
CALL_NUMBER_FROM = "+18452864551"
CALL_NUMBER_TO = "+447823656762"

@app.get("/")
async def index():
    return {"message": "Welcome to the Twilio AI Assistant"}

@app.websocket("/media-stream")
async def media_stream(websocket: WebSocket):
    """Handle WebSocket connection with Twilio and OpenAI for live conversation."""
    print("Client connected")
    await websocket.accept()

    async with websockets.connect(
        "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01",
        extra_headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "OpenAI-Beta": "realtime=v1"}
    ) as openai_ws:

        async def receive_audio_from_twilio():
            """Receive and forward Twilio's audio stream to OpenAI."""
            try:
                async for message in websocket.iter_text():
                    data = json.loads(message)
                    if data.get("event") == "media":
                        audio_data = data["media"]["payload"]
                        await openai_ws.send(json.dumps({"type": "input_audio_buffer.append", "audio": audio_data}))
            except Exception as e:
                print(f"Error receiving from Twilio: {e}")

        async def send_audio_to_twilio():
            """Receive OpenAI's response and send audio back to Twilio."""
            try:
                async for response in openai_ws:
                    data = json.loads(response)
                    if data.get("type") == "response.audio.delta":
                        audio_payload = base64.b64encode(base64.b64decode(data["delta"])).decode("utf-8")
                        await websocket.send_json({"event": "media", "streamSid": "12345", "media": {"payload": audio_payload}})
            except Exception as e:
                print(f"Error sending to Twilio: {e}")

        # Run both send and receive tasks concurrently
        await asyncio.gather(receive_audio_from_twilio(), send_audio_to_twilio())

@app.get("/start-call")
async def start_call():
    """Initiate a call and connect it to the WebSocket."""
    try:
        call = twilio_client.calls.create(
            to=CALL_NUMBER_TO,
            from_=CALL_NUMBER_FROM,
            twiml=f"""<?xml version="1.0" encoding="UTF-8"?>
                <Response>
                    <Connect>
                        <Stream url="wss://evident-orly-onewebonly-4acd77ba.koyeb.app/media-stream"/>
                    </Connect>
                </Response>"""
        )
        return JSONResponse(content={"message": "Call initiated!", "call_sid": call.sid}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
