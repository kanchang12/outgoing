import os
import signal
import sys
from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface

# Retrieve environment variables
agent_id = os.getenv("AGENT_ID")
api_key = os.getenv("ELEVENLABS_API_KEY")

# Check if required environment variables are provided
if not agent_id or not api_key:
    print("Error: AGENT_ID and ELEVENLABS_API_KEY must be set as environment variables.")
    sys.exit(1)

# Initialize ElevenLabs client
client = ElevenLabs(api_key=api_key)

# Initialize Conversation
conversation = Conversation(
    client,
    agent_id,
    requires_auth=bool(api_key),
    audio_interface=DefaultAudioInterface(),
    callback_agent_response=lambda response: print(f"Agent: {response}"),
    callback_agent_response_correction=lambda original, corrected: print(f"Agent: {original} -> {corrected}"),
    callback_user_transcript=lambda transcript: print(f"User: {transcript}"),
)

# Function to handle graceful shutdown (e.g., when Ctrl+C is pressed)
def graceful_shutdown(signum, frame):
    print("\nShutting down the conversation...")
    conversation.stop_session()  # This will end the conversation gracefully
    sys.exit(0)

# Register the signal handler for graceful shutdown (Ctrl+C or SIGINT)
signal.signal(signal.SIGINT, graceful_shutdown)

# Function to monitor the conversation and end when AI detects a stop signal
def monitor_conversation():
    while True:
        # Simulate user input and get AI's response
        user_input = input("You: ").strip()  # Simulate user input to continue conversation
        if user_input:  # Only send the input if it's not empty
            response = conversation.get_response(user_input)  # Get AI response
            print(f"Agent: {response}")
            
            # Check if the AI's response includes phrases indicating the conversation should end
            if any(phrase in response.lower() for phrase in ['goodbye', 'thank you', 'see you', 'take care', 'bye']):
                print("AI: Ending conversation based on response.")
                conversation.stop_session()  # End the conversation gracefully
                break  # Exit the loop and stop the session

# Start the conversation session
conversation.start_session()

# Automatically handle the conversation, let AI detect end-of-conversation signals
monitor_conversation()
