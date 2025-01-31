import sys
import logging
import os
from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation

# Setup logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

# Get environment variables (Agent ID and API key)
AGENT_ID = os.getenv("AGENT_ID")
API_KEY = os.getenv("ELEVENLABS_API_KEY")

# Ensure environment variables are set
if not AGENT_ID or not API_KEY:
    logging.error("Agent ID or API key is missing!")
    sys.exit(1)

# Initialize ElevenLabs client
client = ElevenLabs(api_key=API_KEY)

def place_call(phone_number):
    logging.debug(f"Placing call to phone number: {phone_number}")
    
    try:
        # Set 'requires_auth' based on API_KEY, and no audio interface required
        conversation = Conversation(
            client, 
            AGENT_ID, 
            requires_auth=bool(API_KEY),  # True if API_KEY exists
            audio_interface=None  # No audio interface needed
        )
        
        # Start the conversation
        logging.debug(f"Starting conversation for phone number: {phone_number}")
        conversation.start_session()

        logging.debug(f"Call successfully initiated with agent ID {AGENT_ID}")
        return "Call placed successfully!"
    
    except Exception as e:
        logging.error(f"Error placing call: {str(e)}")
        return f"Error placing call: {str(e)}"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        logging.error("Phone number not provided!")
        sys.exit(1)

    phone_number = sys.argv[1]
    result = place_call(phone_number)
    logging.info(result)
