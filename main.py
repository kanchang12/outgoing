import os
import json
import asyncio
from fastapi import FastAPI
from twilio.rest import Client
from fastapi.responses import JSONResponse
from fastapi import BackgroundTasks
import uvicorn
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

# Twilio API credentials
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
PHONE_NUMBER_FROM = os.getenv("PHONE_NUMBER_FROM")  # Your Twilio phone number

# OpenAI credentials and client
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# FastAPI app instance
app = FastAPI()

# Twilio Client
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# This will be used to start the call
CALL_NUMBER_FROM = '+18452864551'  # The calling number
CALL_NUMBER_TO = '+447823656762'  # The target number you want to call

@app.get('/')
async def index():
    return {"message": "Welcome to the Twilio AI Assistant"}

# This endpoint triggers the outbound call
@app.get('/start-call')
async def start_call(background_tasks: BackgroundTasks):
    try:
        # Creating the Twilio outbound call
        call = twilio_client.calls.create(
            to=CALL_NUMBER_TO,
            from_=CALL_NUMBER_FROM,
            twiml='<Response><Say>Hi! This is a marketing call from our team. We have exciting offers for you!</Say><Pause length="2"/><Say>For more information, visit our website or contact our support team.</Say></Response>'
        )

        background_tasks.add_task(log_call_sid, call.sid)
        return JSONResponse(content={"message": "Call is being initiated!", "call_sid": call.sid}, status_code=200)
    
    except Exception as e:
        return JSONResponse(content={"message": f"Error initiating call: {str(e)}"}, status_code=500)

# Log the call SID for reference
async def log_call_sid(call_sid: str):
    print(f"Call initiated with SID: {call_sid}")

# OpenAI conversation (current API format with gpt-4-turbo)
@app.post('/generate-response')
async def generate_response(user_input: str):
    try:
        formatted_prompt = "You are a marketing assistant providing product offers."
        
        # Send the prompt to OpenAI's GPT-4 Turbo API
        response = openai_client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": formatted_prompt},
                {"role": "user", "content": user_input}
            ],
            max_tokens=150,
            temperature=0.7
        )
        
        # Extract response text
        assistant_reply = response['choices'][0]['message']['content']
        return JSONResponse(content={"message": assistant_reply}, status_code=200)
    
    except Exception as e:
        return JSONResponse(content={"message": f"Error generating response: {str(e)}"}, status_code=500)

import os

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))  # Use the port Koyeb provides
    uvicorn.run(app, host="0.0.0.0", port=port)

