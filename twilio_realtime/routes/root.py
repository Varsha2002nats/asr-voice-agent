"""
FastAPI route for the root endpoint and provider selection.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import os
from loguru import logger

# Import all router modules
from .deepgram import router as deepgram_router
from .openai import router as openai_router
from .openai_demo import router as openai_demo_router
from .deepgram_demo import router as deepgram_demo_router

# Create FastAPI router
router = APIRouter()

# Get provider from environment (defaults to deepgram)
VOICE_PROVIDER = os.getenv("VOICE_PROVIDER", "deepgram").lower()
logger.info(f"Using {VOICE_PROVIDER.upper()} as the voice provider")


@router.get("/", response_class=JSONResponse)
async def index_page():
    """
    Root endpoint for the API.
    """
    return {
        "message": "Blankas bakery is running yayyyy!",
        "voice_provider": VOICE_PROVIDER.upper(),
    }


# Route selection logic
if VOICE_PROVIDER == "deepgram":
    logger.info("Using Deepgram for STT and OpenAI for reasoning (PRODUCTION)")
    router.include_router(deepgram_router)

elif VOICE_PROVIDER == "openai_demo":
    logger.info("Using OpenAI Demo for transcription + manual confirmation (TEST MODE)")
    router.include_router(openai_demo_router)

elif VOICE_PROVIDER == "openai":
    logger.info("Using OpenAI-only router (no Deepgram)")
    router.include_router(openai_router)

elif VOICE_PROVIDER == "deepgram_demo":
    logger.info("Using Deepgram for STT/TTS and OpenAI for LLM (TEST MODE)")
    router.include_router(deepgram_demo_router)

else:
    logger.warning(f"Unrecognized VOICE_PROVIDER '{VOICE_PROVIDER}', defaulting to demo")
    router.include_router(openai_demo_router)
