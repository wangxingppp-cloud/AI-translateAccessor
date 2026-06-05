"""
WebSocket API routes.

The /ws/translate endpoint is the main pipeline for real-time translation:
  - Client sends binary PCM audio chunks + JSON control messages
  - Server sends subtitle JSON (draft → corrected → final) + status + errors

Protocol frames are defined in models/subtitle.py and models/session.py.
"""
import json
import time
import asyncio
import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from ..core.connection_manager import manager
from ..core.session_manager import sessions, SessionState, SessionConfig
from ..models.subtitle import StatusMessage, ErrorMessage
from ..models.glossary import Term

router = APIRouter()

# ── Control message handlers ────────────────────────────────────

async def _handle_start(session_id: str, ws: WebSocket, payload: dict) -> None:
    """Handle start control message — initialize a translation session."""
    config = payload.get("config", {})
    glossary_raw = config.get("glossary", [])

    session_config = SessionConfig(
        source_lang=config.get("source_lang", "en"),
        target_lang=config.get("target_lang", "zh"),
        audio_source=config.get("audio_source", "microphone"),
        enable_correction=config.get("enable_correction", True),
        glossary_terms=[Term(**t) for t in glossary_raw],
    )

    try:
        sessions.create(session_id, session_config)
    except RuntimeError as e:
        await ws.send_json(
            ErrorMessage(code="SESSION_LIMIT", message=str(e)).model_dump()
        )
        return

    sessions.update_state(session_id, SessionState.LISTENING)
    await ws.send_json(
        StatusMessage(
            status="listening",
            message=f"Session started: {session_config.source_lang} → {session_config.target_lang}",
        ).model_dump()
    )
    logger.info(f"Session [{session_id}] started ({session_config.source_lang}→{session_config.target_lang})")


async def _handle_pause(session_id: str, _ws: WebSocket, _payload: dict) -> None:
    """Handle pause — suspend audio processing."""
    try:
        sessions.update_state(session_id, SessionState.PAUSED)
    except KeyError:
        pass


async def _handle_resume(session_id: str, _ws: WebSocket, _payload: dict) -> None:
    """Handle resume — continue audio processing."""
    try:
        sessions.update_state(session_id, SessionState.LISTENING)
    except KeyError:
        pass


async def _handle_stop(session_id: str, ws: WebSocket, _payload: dict) -> None:
    """Handle stop — end the translation session."""
    try:
        sessions.update_state(session_id, SessionState.ENDED)
        session = sessions.get(session_id)
        if session:
            await ws.send_json(
                StatusMessage(
                    status="idle",
                    message=f"Session ended: {session.total_sentences} sentences, {session.total_audio_chunks} chunks",
                ).model_dump()
            )
        sessions.remove(session_id)
    except KeyError:
        pass


async def _handle_update_glossary(session_id: str, _ws: WebSocket, payload: dict) -> None:
    """Handle dynamic glossary update mid-session."""
    try:
        session = sessions.require(session_id)
        terms_raw = payload.get("terms", [])
        session.config.glossary_terms = [Term(**t) for t in terms_raw]
    except KeyError:
        pass


async def _handle_ping(_session_id: str, ws: WebSocket, _payload: dict) -> None:
    """Respond to client heartbeat."""
    await ws.send_json({"type": "pong", "timestamp": time.time()})


# Control message router
_CONTROL_HANDLERS = {
    "start": _handle_start,
    "pause": _handle_pause,
    "resume": _handle_resume,
    "stop": _handle_stop,
    "update_glossary": _handle_update_glossary,
    "ping": _handle_ping,
}


async def _process_control_message(session_id: str, ws: WebSocket, text: str) -> None:
    """Parse and route a JSON control message."""
    try:
        message = json.loads(text)
    except json.JSONDecodeError:
        await ws.send_json(
            ErrorMessage(code="INVALID_JSON", message="Could not parse control message").model_dump()
        )
        return

    msg_type = message.get("type", "")
    handler = _CONTROL_HANDLERS.get(msg_type)

    if handler:
        await handler(session_id, ws, message)
    else:
        logger.warning(f"Unknown control message type: {msg_type}")


async def _process_audio_chunk(session_id: str, ws: WebSocket, data: bytes) -> None:
    """Process an audio chunk.

    Placeholder — will be wired to Sherpa-onnx ASR engine in ASR module.
    Currently: acknowledges receipt and tracks metrics.
    """
    try:
        session = sessions.require(session_id)
    except KeyError:
        # Session not started yet — send error
        await ws.send_json(
            ErrorMessage(
                code="NO_SESSION",
                message="Send a 'start' control message before audio data",
            ).model_dump()
        )
        return

    if session.state != SessionState.LISTENING:
        return  # Silently drop audio when paused / ended

    sessions.record_audio_chunk(session_id)

    # Placeholder response (will be replaced by ASR → translation pipeline)
    # Currently sends a status update every 50 chunks (~10s at 200ms/chunk)
    if session.total_audio_chunks % 50 == 0:
        await ws.send_json(
            StatusMessage(
                status="listening",
                message=f"Audio chunks received: {session.total_audio_chunks}",
            ).model_dump()
        )


# ── Main WebSocket endpoint ──────────────────────────────────────

@router.websocket("/ws/translate")
async def translate_websocket(websocket: WebSocket):
    """
    Main translation WebSocket endpoint.

    Client → Server:
      Binary: 16-bit PCM audio, 16kHz, mono, 200ms chunks
      Text (JSON): {"type": "start"|"pause"|"resume"|"stop"|"update_glossary"|"ping", ...}

    Server → Client (JSON):
      subtitle_draft  — NMT initial translation (real-time)
      subtitle_corrected — LLM-corrected translation (async)
      subtitle_final — finalized sentence
      status         — pipeline status + metrics
      error          — error with recovery info
      pong           — heartbeat response
    """
    now = time.time()

    # Check capacity — accept then reject if full
    if sessions.is_at_capacity:
        await websocket.accept()
        await websocket.send_json(
            ErrorMessage(
                code="SERVER_BUSY",
                message=f"Max concurrent sessions reached",
            ).model_dump()
        )
        await websocket.close()
        return

    # Accept the WebSocket (required before sending)
    await websocket.accept()

    # Register session
    session_id = str(uuid.uuid4())
    await manager.connect(session_id, websocket)

    await websocket.send_json(
        StatusMessage(
            status="idle",
            message="Connected. Send 'start' to begin translation.",
        ).model_dump()
    )

    try:
        while True:
            # Receive either binary (audio) or text (control) frames
            data = await websocket.receive()

            if "text" in data:
                await _process_control_message(session_id, websocket, data["text"])

            elif "bytes" in data:
                await _process_audio_chunk(session_id, websocket, data["bytes"])

    except WebSocketDisconnect:
        logger.info(f"Session [{session_id}] disconnected")
    except Exception as e:
        logger.error(f"Session [{session_id}] error: {e}")
        try:
            await websocket.send_json(
                ErrorMessage(
                    code="INTERNAL_ERROR",
                    message=str(e),
                    recoverable=False,
                    timestamp=time.time(),
                ).model_dump()
            )
        except Exception:
            pass
    finally:
        # Cleanup
        sessions.remove(session_id)
        manager.disconnect(session_id)
        elapsed = time.time() - now
        logger.info(f"Session [{session_id}] cleaned up (duration: {elapsed:.1f}s, active: {sessions.active_count})")
