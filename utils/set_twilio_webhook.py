import os
from dotenv import load_dotenv
from twilio.rest import Client

# Load from .env file
load_dotenv()

# Get config values
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
api_key_sid = os.getenv("TWILIO_API_KEY_SID")
api_secret = os.getenv("TWILIO_API_SECRET")
phone_number = os.getenv("TWILIO_NUMBER")
webhook_url = os.getenv(
    "WEBHOOK_URL", "https://ngngngngng.ngrok-free.app"
)

# Initialize Twilio client with API Key/Secret
client = Client(api_key_sid, api_secret, account_sid)

# Find the number and update the webhook
matching_numbers = client.incoming_phone_numbers.list(phone_number=phone_number)

if not matching_numbers:
    raise Exception(f"No phone number {phone_number} found in Twilio account.")

matching_numbers[0].update(voice_url=webhook_url, voice_method="POST")

print(f"✅ Webhook for {phone_number} updated to: {webhook_url}")
