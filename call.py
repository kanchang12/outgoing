import sys
import os
from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface

# Ensure environment variables are set
API_KEY = os.getenv("ELEVENLABS_API_KEY")
AGENT_ID = os.getenv("AGENT_ID")

# Extract the phone number from the command line arguments
phone_number = sys.argv[1]

# Initialize ElevenLabs client
client = ElevenLabs(api_key=API_KEY)

# Create a conversation
conversation = Conversation(
    client,
    AGENT_ID,
    requires_auth=bool(API_KEY),
    audio_interface=DefaultAudioInterface(),
    callback_agent_response=lambda response: print(f"Agent: {response}"),
    callback_user_transcript=lambda transcript: print(f"User: {transcript}")
)

# Assuming you would add code here to trigger the call based on the phone number

# Start the conversation session
conversation.start_session()

# Example: Set up the callback for handling the conversation
# This is a placeholder where you might add the code to trigger a voice call

# Clean shutdown when the session ends
conversation.wait_for_session_end()
