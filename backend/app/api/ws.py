"""
WebSocket API routes.

The /ws/translate endpoint is the main pipeline for real-time translation:
audio binary frames in → subtitle JSON out.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from ..core.connection_manager import manager

router = APIRouter()


@router.websocket("/ws/translate")
async def translate_websocket(websocket: WebSocket):
    """
    Main translation WebSocket endpoint.

    Client sends:
      - Binary frames: 16-bit PCM audio chunks (16kHz, mono)
      - Text frames (JSON): control messages (start, pause, resume, stop, ping)

    Server sends (JSON):
      - subtitle_draft: NMT initial translation
      - subtitle_corrected: LLM-corrected translation
      - subtitle_final: final sentence translation
      - status: processing status and metrics
      - error: error notifications with recovery info
      - pong: heartbeat response
    """
    await manager.connect("pending", websocket)
    try:
        while True:
            # Accept either binary (audio) or text (control) frames
            data = await websocket.receive()

            if "text" in data:
                message = data["text"]
                # Control message handling — will be implemented in WebSocket module
                logger.debug(f"Received text message: {message[:100]}")
                await websocket.send_json({
                    "type": "status",
                    "status": "idle",
                    "message": "WebSocket connected — pipeline not yet active",
                })

            elif "bytes" in data:
                # Audio chunk received — pipeline will be wired in ASR module
                logger.debug(f"Received audio chunk: {len(data['bytes'])} bytes")
                # Placeholder: echo back for connectivity verification
                await websocket.send_json({
                    "type": "status",
                    "status": "listening",
                    "message": f"Audio chunk received ({len(data['bytes'])} bytes)",
                })

    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        manager.disconnect("pending")
