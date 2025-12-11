"""
Main FastAPI application.
"""

from fastapi import FastAPI, APIRouter
from loguru import logger

from .config.settings import PORT
from .routes.root import router

# Create FastAPI app
app = FastAPI()


# Get the active provider router and include it
app.include_router(router)


def start():
    """
    Start the FastAPI server.
    """
    import uvicorn

    logger.info(f"Starting server on port {PORT}")
    uvicorn.run("twilio_realtime.app:app", host="0.0.0.0", port=PORT, reload=True)


if __name__ == "__main__":
    start()
