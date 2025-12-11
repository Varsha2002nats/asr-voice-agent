"""
FastAPI routes for handling Twilio calls with Deepgram for real-time transcription and speech, using GPT as the LLM.
"""

import asyncio
import base64
import json
import time
import websockets
from fastapi import APIRouter, Request, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.websockets import WebSocketDisconnect
from loguru import logger
from twilio.twiml.voice_response import Connect, VoiceResponse
from twilio.rest import Client

from ..config.settings import (
    LOG_EVENT_TYPES,
    SHOW_TIMING_MATH,
    DEEPGRAM_API_KEY,
    TWILIO_ACCOUNT_SID,
    TWILIO_PHONE_NUMBER,
    TWILIO_AUTH_TOKEN,
)
from ..models.connection_store import connections
from ..utils.transcript_logger import confirm_and_log
from ..config.prompts_simple import SYSTEM_MESSAGE_TEMPLATE

router = APIRouter()


@router.api_route("/", methods=["POST"])
async def handle_incoming_call(request: Request):
    """
    Handle incoming call and return TwiML response to connect to Media Stream.

    Args:
        request: The FastAPI request object

    Returns:
        HTMLResponse: TwiML response with media stream connection
    """
    form_data = await request.form()
    caller_phone = form_data.get("From", "Unknown")
    logger.debug(f"Incoming call from: {caller_phone}")

    call_sid = form_data.get("CallSid", "unknown-call")
    connections.add_connection(
        call_sid,
        {
            "phone": caller_phone,
            "timestamp": asyncio.get_event_loop().time(),
            "start_time": time.time(),
            "messages": [],
        },
    )
    logger.debug(f"Stored caller info in connection store with key: {call_sid}")

    response = VoiceResponse()
    connect = Connect()
    host = request.url.hostname
    stream_url = f"wss://{host}/deepgram-media-stream?call_sid={call_sid}"
    logger.debug(f"Stream url: {stream_url}")

    connect.stream(
        url=stream_url, track="inbound_track", parameters={"call_sid": call_sid}
    )
    response.append(connect)
    return HTMLResponse(content=str(response), media_type="application/xml")


@router.websocket("/deepgram-media-stream")
async def handle_media_stream(websocket: WebSocket):
    """
    Handle WebSocket connections between Twilio and Deepgram.

    Args:
        websocket: The WebSocket connection from Twilio
    """
    await websocket.accept()
    logger.info("Twilio client connected")

    connection_state = {
        "call_sid": None,
        "caller_phone": "Unknown",
        "deepgram_ws": None,
        "stream_sid": None,
        "latest_media_timestamp": 0,
        "mark_queue": [],
        "audio_queue": asyncio.Queue(),
        "connection_active": True,
        "start_data": None,
        "tasks": [],
        "speech_started": False,
        "last_assistant_item": None,
        "response_start_timestamp_twilio": None,
    }

    await initialize_connection_state(websocket, connection_state)
    logger.info(f"WebSocket connection for caller: {connection_state['caller_phone']}")

    max_retries = 3
    retry_delay = 1  # seconds
    for attempt in range(max_retries):
        try:
            async with websockets.connect(
                "wss://agent.deepgram.com/v1/agent/converse",
                subprotocols=["token", DEEPGRAM_API_KEY],
                ping_interval=5,
                ping_timeout=10,
            ) as deepgram_ws:
                connection_state["deepgram_ws"] = deepgram_ws
                logger.debug(f"Deepgram WebSocket connection attempt {attempt + 1} successful")
                await initialize_deepgram_session(
                    deepgram_ws, connection_state.get("caller_phone")
                )

                twilio_task = asyncio.create_task(
                    receive_from_twilio(websocket, connection_state)
                )
                deepgram_task = asyncio.create_task(
                    receive_from_deepgram(websocket, connection_state)
                )
                deepgram_sender_task = asyncio.create_task(
                    send_to_deepgram(connection_state)
                )

                connection_state["tasks"] = [
                    twilio_task,
                    deepgram_task,
                    deepgram_sender_task,
                ]

                done, pending = await asyncio.wait(
                    connection_state["tasks"], return_when=asyncio.FIRST_COMPLETED
                )

                for task in pending:
                    task.cancel()

                logger.info("One of the communication tasks has ended")
                break  # Exit retry loop on success

        except websockets.exceptions.InvalidHandshake as e:
            logger.error(f"Deepgram WebSocket handshake failed: {e}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying Deepgram connection in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error("Max retries reached for Deepgram connection")
        except websockets.exceptions.ConnectionClosed as e:
            logger.error(f"Deepgram WebSocket connection closed unexpectedly: {e}")
        except Exception as e:
            logger.error(f"Connection error: {str(e)}")
            if "name" in str(e).lower():
                logger.error("Possible JSON parsing issue in Deepgram response")
        finally:
            if attempt == max_retries - 1 or not connection_state["connection_active"]:
                await cleanup_connection(connection_state)
                break


async def initialize_connection_state(websocket, connection_state):
    """
    Initialize the connection state with data from the start event.

    Args:
        websocket: The WebSocket connection
        connection_state: Dictionary holding connection state
    """
    try:
        start_message = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
        data = json.loads(start_message)
        if data["event"] == "start":
            connection_state["call_sid"] = data["start"].get("callSid") or data[
                "start"
            ].get("streamSid")
            logger.debug(
                f"Got call_sid from start event: {connection_state['call_sid']}"
            )

            connection_data = connections.get_connection(connection_state["call_sid"])
            if connection_data and "phone" in connection_data:
                connection_state["caller_phone"] = connection_data["phone"]
                logger.debug(
                    f"Retrieved caller phone from store: {connection_state['caller_phone']}"
                )

        connection_state["start_data"] = data

    except (asyncio.TimeoutError, json.JSONDecodeError, KeyError) as e:
        logger.error(f"Error getting start event: {e}")
        connection_state["caller_phone"] = "Unknown Caller"
        connection_state["start_data"] = None


async def initialize_deepgram_session(deepgram_ws, caller_phone):
    """
    Initialize the Deepgram session with necessary configuration.

    Args:
        deepgram_ws: The WebSocket connection to Deepgram
        caller_phone: The caller's phone number
    """
    if not DEEPGRAM_API_KEY:
        logger.error("DEEPGRAM_API_KEY is not set")
        raise ValueError("DEEPGRAM_API_KEY is required")

    system_prompt = SYSTEM_MESSAGE_TEMPLATE.format(caller_phone=caller_phone)
    config_message = {
        "type": "Settings",
        "audio": {
            "input": {
                "encoding": "mulaw",
                "sample_rate": 8000,
            },
            "output": {
                "encoding": "mulaw",
                "sample_rate": 8000,
                "container": "none",
            },
        },
        "agent": {
            "language": "en",
            "listen": {
                "provider": {
                    "type": "deepgram",
                    "model": "nova-3",
                }
            },
            "think": {
                "provider": {
                    "type": "open_ai",
                    "model": "gpt-4o-mini",
                    "temperature": 0.7,
                },
                "prompt": system_prompt,
            },
            "speak": {"provider": {"type": "deepgram", "model": "aura-2-thalia-en"}},
            "greeting": "Hello! Thank you for calling Blanka's Bakery. How can I help you today?",
        },
    }

    try:
        logger.debug(f"Sending Deepgram config message: {json.dumps(config_message, indent=2)}")
        await deepgram_ws.send(json.dumps(config_message))
        logger.info("Sent initial greeting to Deepgram")
        # Receive initial response to verify connection
        initial_response = await asyncio.wait_for(deepgram_ws.recv(), timeout=5.0)
        logger.debug(f"Received initial Deepgram response: {initial_response}")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to serialize config message: {e}")
        raise
    except asyncio.TimeoutError:
        logger.error("Timeout waiting for Deepgram initial response")
        raise
    except Exception as e:
        logger.error(f"Error initializing Deepgram session: {e}")
        raise


async def receive_from_twilio(websocket, connection_state):
    """
    Receive audio data from Twilio and queue it for Deepgram.

    Args:
        websocket: The WebSocket connection from Twilio
        connection_state: Dictionary holding connection state
    """
    BUFFER_SIZE = 20 * 160  # 0.4 seconds of audio
    inbuffer = bytearray(b"")

    if (
        connection_state["start_data"]
        and connection_state["start_data"]["event"] == "start"
    ):
        connection_state["stream_sid"] = connection_state["start_data"]["start"][
            "streamSid"
        ]
        logger.info(
            f"Incoming stream has started {connection_state['stream_sid']}"
        )
        connection_state["latest_media_timestamp"] = 0

    try:
        while connection_state["connection_active"]:
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
                data = json.loads(message)

                if data["event"] == "media":
                    connection_state["latest_media_timestamp"] = int(
                        data.get("media", {}).get("timestamp", 0)
                    )

                    media = data["media"]
                    chunk = base64.b64decode(media["payload"])

                    if media.get("track") == "inbound":
                        inbuffer.extend(chunk)

                        while len(inbuffer) >= BUFFER_SIZE:
                            audio_chunk = inbuffer[:BUFFER_SIZE]
                            await connection_state["audio_queue"].put(audio_chunk)
                            inbuffer = inbuffer[BUFFER_SIZE:]

                elif data["event"] == "start":
                    await handle_start_event(data, connection_state)
                elif data["event"] == "mark":
                    if connection_state["mark_queue"]:
                        connection_state["mark_queue"].pop(0)
                elif data["event"] == "stop":
                    logger.info("Stop event received from Twilio")
                    connection_state["connection_active"] = False
                    break

            except asyncio.TimeoutError:
                try:
                    pong = await websocket.receive_text()
                except Exception:
                    logger.info("Twilio connection appears to be closed (timeout)")
                    connection_state["connection_active"] = False
                    break
    except WebSocketDisconnect:
        logger.info("Twilio client disconnected (WebSocketDisconnect).")
        connection_state["connection_active"] = False
    except Exception as e:
        logger.error(f"Error in receive_from_twilio: {e}")
        connection_state["connection_active"] = False


async def send_to_deepgram(connection_state):
    """
    Send audio data from queue to Deepgram.

    Args:
        connection_state: Dictionary holding connection state
    """
    try:
        while connection_state["connection_active"]:
            audio_chunk = await connection_state["audio_queue"].get()
            if (
                connection_state["deepgram_ws"]
                and not connection_state["deepgram_ws"].closed
            ):
                await connection_state["deepgram_ws"].send(audio_chunk)
    except Exception as e:
        logger.error(f"Error in send_to_deepgram: {e}")
        connection_state["connection_active"] = False


async def receive_from_deepgram(websocket, connection_state):
    """
    Receive messages from Deepgram and forward audio to Twilio.

    Args:
        websocket: The WebSocket connection to Twilio
        connection_state: Dictionary holding connection state
    """
    try:
        async for message in connection_state["deepgram_ws"]:
            if not connection_state["connection_active"]:
                logger.info(
                    "Connection marked as inactive, stopping receive_from_deepgram"
                )
                break

            if isinstance(message, str):
                try:
                    data = json.loads(message)
                    event = data.get("type", None)
                    if event.lower() == "conversationtext":
                        logger.info(f"Received conversation text: {data}")
                        role = data.get("role")
                        content = data.get("content")
                        if role and content:
                            connections.add_message(
                                connection_state["call_sid"],
                                role,
                                content,
                                time.time(),
                            )
                            if role == "assistant":
                                connection_state["last_assistant_item"] = data.get("item_id")
                                if connection_state["response_start_timestamp_twilio"] is None:
                                    connection_state["response_start_timestamp_twilio"] = (
                                        connection_state["latest_media_timestamp"]
                                    )
                                    if SHOW_TIMING_MATH:
                                        logger.debug(
                                            f"Setting start timestamp for new response: {connection_state['response_start_timestamp_twilio']}ms"
                                        )
                    
                    elif event.lower() == "functioncall":
                        func_name = data.get("name")
                        params = data.get("parameters", {})
                        if func_name == "store_contact_info":
                            name = params.get("name")
                            email = params.get("email", "")
                            logger.info(f"[FunctionCall] Captured → Name: {name}, Email: {email}")
                            connections.add_message(
                                connection_state["call_sid"],
                                "assistant",
                                f"Captured via function: name={name}, email={email}",
                                time.time(),
                            )

                    elif event == "UserStartedSpeaking":
                        connection_state["speech_started"] = True
                        if (
                            connection_state["stream_sid"]
                            and connection_state["last_assistant_item"]
                            and connection_state["response_start_timestamp_twilio"] is not None
                        ):
                            elapsed_time = (
                                connection_state["latest_media_timestamp"]
                                - connection_state["response_start_timestamp_twilio"]
                            )
                            if SHOW_TIMING_MATH:
                                logger.debug(
                                    f"Truncating item at {elapsed_time}ms"
                                )
                            truncate_event = {
                                "type": "conversation.item.truncate",
                                "item_id": connection_state["last_assistant_item"],
                                "content_index": 0,
                                "audio_end_ms": elapsed_time,
                            }
                            await connection_state["deepgram_ws"].send(json.dumps(truncate_event))
                            await websocket.send_json(
                                {"event": "clear", "streamSid": connection_state["stream_sid"]}
                            )
                            connection_state["mark_queue"].clear()
                            connection_state["last_assistant_item"] = None
                            connection_state["response_start_timestamp_twilio"] = None
                            logger.info("Sent clear message due to user speaking")

                except json.JSONDecodeError:
                    logger.error(f"Failed to parse Deepgram message: {message}")

            else:
                if connection_state["stream_sid"]:
                    connection_state["speech_started"] = False
                    raw_mulaw = message
                    audio_payload = base64.b64encode(raw_mulaw).decode("utf-8")
                    media_message = {
                        "event": "media",
                        "streamSid": connection_state["stream_sid"],
                        "media": {"payload": audio_payload},
                    }
                    await websocket.send_json(media_message)
                    await send_mark(websocket, connection_state)

    except websockets.exceptions.ConnectionClosed:
        logger.info("Deepgram WebSocket connection closed normally")
        connection_state["connection_active"] = False
    except Exception as e:
        logger.error(f"Error in receive_from_deepgram: {e}")
        connection_state["connection_active"] = False


async def handle_start_event(data, connection_state):
    """
    Handle start events from Twilio.

    Args:
        data: The start event data
        connection_state: Dictionary holding connection state
    """
    connection_state["stream_sid"] = data["start"]["streamSid"]
    logger.info(f"Incoming stream has started {connection_state['stream_sid']}")

    if not connection_state["call_sid"]:
        connection_state["call_sid"] = (
            data["start"].get("callSid") or connection_state["stream_sid"]
        )
        connection_data = connections.get_connection(connection_state["call_sid"])
        if connection_data and "phone" in connection_data:
            connection_state["caller_phone"] = connection_data["phone"]
            logger.debug(
                f"Retrieved caller phone from store: {connection_state['caller_phone']}"
            )

    connection_state["latest_media_timestamp"] = 0
    connection_state["last_assistant_item"] = None
    connection_state["response_start_timestamp_twilio"] = None


async def send_mark(websocket, connection_state):
    """
    Send a mark event to track the response parts.

    Args:
        websocket: The WebSocket connection to Twilio
        connection_state: Dictionary holding connection state
    """
    if connection_state["stream_sid"]:
        mark_event = {
            "event": "mark",
            "streamSid": connection_state["stream_sid"],
            "mark": {"name": "responsePart"},
        }
        await websocket.send_json(mark_event)
        connection_state["mark_queue"].append("responsePart")


async def cleanup_connection(connection_state):
    """
    Clean up the connection and resources.

    Args:
        connection_state: Dictionary holding connection state
    """
    logger.info("Closing WebSocket connection and generating transcript")

    for task in connection_state["tasks"]:
        if not task.done():
            task.cancel()

    if connection_state["call_sid"]:
        transcript_text = print_call_transcript(
            connection_state["call_sid"], connection_state["caller_phone"]
        )
        logger.info(f"Transcript:\n{transcript_text}")

        num_user_no = transcript_text.lower().count("user: no")
        attempt_number = 2 if num_user_no >= 1 else 1
        confirm_and_log(connection_state["call_sid"], transcript_text, attempt_number=attempt_number)

    if connection_state["deepgram_ws"] and not connection_state["deepgram_ws"].closed:
        try:
            await connection_state["deepgram_ws"].close()
            logger.info("Closed Deepgram WebSocket connection")
        except Exception as close_error:
            logger.error(f"Error closing Deepgram connection: {close_error}")


def print_call_transcript(call_sid, caller_phone) -> str:
    """
    Print a formatted transcript of the call conversation.

    Args:
        call_sid: The unique identifier for the call
        caller_phone: The phone number of the caller

    Returns:
        str: The formatted transcript text
    """
    transcript_text = ""
    connection_data = connections.get_connection(call_sid)
    if connection_data and "messages" in connection_data:
        messages = connection_data["messages"]
        start_time = connection_data.get("start_time", 0)
        end_time = time.time()
        duration = end_time - start_time

        header = f"\nCALL TRANSCRIPT - {caller_phone}\n"
        header += f"Call duration: {int(duration // 60)}:{int(duration % 60):02d}\n"
        transcript_text += header

        print("\n" + "-" * 80)
        print(header)
        print("-" * 80)

        for idx, msg in enumerate(messages):
            role = msg["role"].upper()
            content = msg["content"]
            timestamp = msg.get("timestamp")
            time_str = ""
            if timestamp:
                time_str = f"[{time.strftime('%H:%M:%S', time.localtime(timestamp))}] "

            message_line = f"{time_str}{role}: {content}"
            transcript_text += message_line + "\n"

            print(message_line)
            if idx < len(messages) - 1:
                print("-" * 40)

        print("-" * 80 + "\n")
        return transcript_text

    return "No transcript available."