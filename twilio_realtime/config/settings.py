"""
Configuration settings for the OpenAI realtime API integration.
"""

import os
from dotenv import load_dotenv
from ..utils.utils import parse_bool

# Load environment variables from .env file
load_dotenv()

# API Keys and service configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PORT = int(os.getenv("PORT", 5002))

# Voice and response settings
VOICE = "alloy"

# Logging configuration
LOG_EVENT_TYPES = [
    "error",
    "response.content.done",
    "rate_limits.updated",
    "response.done",
    "input_audio_buffer.committed",
    "input_audio_buffer.speech_stopped",
    "input_audio_buffer.speech_started",
    "session.created",
]
SHOW_TIMING_MATH = False

# OpenAI API connection settings
OPENAI_REALTIME_URL = (
    "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"
)

# Twilio SMS settings
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID_2")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN_2")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER_2")  # Your Twilio phone number

# Deepgram API settings
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
DEEPGRAM_API_URL = os.getenv("DEEPGRAM_API_URL", "wss://api.deepgram.com/v1/listen")

SEND_SMS = parse_bool(os.getenv("SEND_SMS", "false"))
