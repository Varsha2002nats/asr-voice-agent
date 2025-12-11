"""
OpenAI API service for real-time conversation.
"""

import asyncio
import json
import websockets

from loguru import logger

from ..config.settings import OPENAI_API_KEY, OPENAI_REALTIME_URL, VOICE
from ..utils.transcript_processor import extract_order_details


async def initialize_session(openai_ws, caller_phone=None):
    """
    Control initial session with OpenAI.

    Args:
        openai_ws: WebSocket connection to OpenAI API
        caller_phone: Optional phone number of the caller
    """
    from ..utils.prompt_generator import generate_system_message

    # Generate system message with caller's phone number if available
    system_message = generate_system_message(caller_phone)
    #logger.warning(f"System message: {system_message}")

    session_update = {
        "type": "session.update",
        "session": {
            "turn_detection": {"type": "server_vad"},
            "input_audio_format": "g711_ulaw",
            "output_audio_format": "g711_ulaw",
            "voice": VOICE,
            "instructions": system_message,
            "modalities": ["text", "audio"],
            "input_audio_transcription": {"model": "whisper-1"},
            "temperature": 0.6,
        },
    }

    await openai_ws.send(json.dumps(session_update))

    # Start conversation with AI speaking first
    await send_initial_conversation_item(openai_ws)


# async def send_initial_conversation_item(openai_ws):
#     """
#     Send initial conversation item if AI talks first.

#     Args:
#         openai_ws: WebSocket connection to OpenAI API
#     """
#     initial_conversation_item = {
#         "type": "conversation.item.create",
#         "item": {
#             "type": "message",
#             "role": "user",
#             "content": [
#                 {
#                     "type": "input_text",
#                     "text": "Hello from Blankas Bakery, how can I help you today?",
#                 }
#             ],
#         },
#     }
#     await openai_ws.send(json.dumps(initial_conversation_item))
#     await openai_ws.send(json.dumps({"type": "response.create"}))

async def send_initial_conversation_item(openai_ws):
    """
    Start the conversation with the AI speaking first.
    """
    initial_message = {
        "type": "conversation.item.create",
        "item": {
            "type": "message",
            "role": "assistant",
            "content": [
                {
                    "type": "output_text",
                    "text": "Hello! This is Blanka’s Bakery. May I have your full name, please?",
                }
            ],
        },
    }

    # Send message to OpenAI
    await openai_ws.send(json.dumps(initial_message))

    # Ask OpenAI to speak it
    await openai_ws.send(json.dumps({
        "type": "response.create"
    }))


async def process_transcript(openai_ws, caller_phone):
    """
    Request and process the full transcript at the end of the call.

    Args:
        openai_ws: WebSocket connection to OpenAI API
        caller_phone: Phone number of the caller

    Returns:
        dict: Extracted order information or None if processing failed
    """
    print(f"Processing transcript for caller: {caller_phone}")

    # Request the full conversation transcript
    transcript_request = {
        "type": "conversation.get",
    }

    await openai_ws.send(json.dumps(transcript_request))

    # Get the response with full conversation
    response = await openai_ws.recv()
    conversation_data = json.loads(response)

    if conversation_data.get("type") == "conversation" and "items" in conversation_data:
        # Build the transcript from conversation items
        full_transcript = ""

        for item in conversation_data["items"]:
            role = item.get("role", "")

            if role == "user":
                speaker = "Customer"
            elif role == "assistant":
                speaker = "Assistant"
            else:
                speaker = role.capitalize()

            if "content" in item:
                for content in item["content"]:
                    if content.get("type") == "text":
                        full_transcript += f"{speaker}: {content.get('text', '')}\n"

        # Extract order details
        order_info = extract_order_details(full_transcript)

        # Print the extracted information
        print("\n===== CALL SUMMARY =====")
        print(f"Caller Phone: {caller_phone}")
        print(f"Extracted Name: {order_info['name']}")
        print(f"Extracted Email: {order_info['email']}")
        print(f"Extracted Phone: {order_info['phone']}")
        print(f"Pickup Date: {order_info['pickup_date']}")

        if order_info["products"]:
            print("Order Items:")
            for product in order_info["products"]:
                print(f"  - {product}")

        print("=======================\n")

        return order_info

    return None


async def create_openai_connection():
    """
    Create a connection to the OpenAI Realtime API.

    Returns:
        WebSocketClientProtocol: An open websocket connection to OpenAI
    """
    return await websockets.connect(
        OPENAI_REALTIME_URL,
        extra_headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "OpenAI-Beta": "realtime=v1",
        },
    )
