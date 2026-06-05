"""
WebSocket API routes.

The /ws/translate endpoint is the main pipeline for real-time translation:
  - Client sends binary PCM audio chunks + JSON control messages
  - Server sends subtitle JSON (draft → corrected → final) + status + errors

Pipeline:  PCM bytes → float32 → VAD → ASR → subtitle_draft → client

Protocol frames are defined in models/subtitle.py and models/session.py.
"""
import json
import time
import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from ..core.connection_manager import manager
from ..core.session_manager import sessions, SessionState, SessionConfig
from ..models.subtitle import (
    StatusMessage, ErrorMessage, SubtitleDraft, SubtitleFinal,
)
from ..models.glossary import Term
from ..engines.asr.stream_handler import StreamHandler

router = APIRouter()

# ── Per-session ASR handlers ────────────────────────────────────

_session_handlers: dict[str, StreamHandler] = {}


def _get_handler(session_id: str, create: bool = False) -> StreamHandler | None:
    """Get or create a StreamHandler for a session."""
    if session_id not in _session_handlers and create:
        _session_handlers[session_id] = StreamHandler()
    return _session_handlers.get(session_id)


def _remove_handler(session_id: str) -> None:
    handler = _session_handlers.pop(session_id, None)
    if handler:
        handler.reset()


# ── Control message handlers ────────────────────────────────────

async def _handle_start(session_id: str, ws: WebSocket, payload: dict) -> None:
    """Handle start — initialize session and ASR handler."""
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

    # Initialize ASR handler
    _get_handler(session_id, create=True)

    sessions.update_state(session_id, SessionState.LISTENING)
    await ws.send_json(
        StatusMessage(
            status="listening",
            message=f"Session started: {session_config.source_lang} → {session_config.target_lang}",
        ).model_dump()
    )
    logger.info(f"Session [{session_id}] started ({session_config.source_lang}→{session_config.target_lang})")


async def _handle_pause(session_id: str, _ws: WebSocket, _payload: dict) -> None:
    try:
        sessions.update_state(session_id, SessionState.PAUSED)
    except KeyError:
        pass


async def _handle_resume(session_id: str, _ws: WebSocket, _payload: dict) -> None:
    try:
        sessions.update_state(session_id, SessionState.LISTENING)
    except KeyError:
        pass


async def _handle_stop(session_id: str, ws: WebSocket, _payload: dict) -> None:
    """Handle stop — flush ASR buffer and clean up."""
    try:
        # Flush any pending ASR results before ending
        handler = _get_handler(session_id)
        if handler and handler.has_pending_speech():
            final_result = await handler.flush()
            if final_result and final_result.text:
                await ws.send_json(
                    SubtitleFinal(
                        sequence_id=str(uuid.uuid4()),
                        original=final_result.text,
                        translated="",  # Will be filled by translation module
                        confidence=final_result.confidence,
                        timestamp=final_result.timestamp,
                    ).model_dump()
                )

        session = sessions.get(session_id)
        if session:
            await ws.send_json(
                StatusMessage(
                    status="idle",
                    message=f"Session ended: {session.total_sentences} sentences, {session.total_audio_chunks} chunks",
                ).model_dump()
            )

        _remove_handler(session_id)
        sessions.remove(session_id)
    except KeyError:
        pass


async def _handle_update_glossary(session_id: str, _ws: WebSocket, payload: dict) -> None:
    try:
        session = sessions.require(session_id)
        terms_raw = payload.get("terms", [])
        session.config.glossary_terms = [Term(**t) for t in terms_raw]
    except KeyError:
        pass


async def _handle_ping(_session_id: str, ws: WebSocket, _payload: dict) -> None:
    await ws.send_json({"type": "pong", "timestamp": time.time()})


_CONTROL_HANDLERS = {
    "start": _handle_start,
    "pause": _handle_pause,
    "resume": _handle_resume,
    "stop": _handle_stop,
    "update_glossary": _handle_update_glossary,
    "ping": _handle_ping,
}


async def _process_control_message(session_id: str, ws: WebSocket, text: str) -> None:
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
    """Process audio chunk through the ASR pipeline.

    PCM bytes → float32 samples → VAD → ASR decode → subtitle_draft → client
    """
    try:
        session = sessions.require(session_id)
    except KeyError:
        await ws.send_json(
            ErrorMessage(
                code="NO_SESSION",
                message="Send a 'start' control message before audio data",
            ).model_dump()
        )
        return

    if session.state != SessionState.LISTENING:
        return

    sessions.record_audio_chunk(session_id)

    handler = _get_handler(session_id)
    if not handler:
        return

    try:
        async for result in handler.process_chunk(data):
            if result.text:
                sessions.record_sentence(session_id)
                await ws.send_json(
                    SubtitleDraft(
                        sequence_id=str(uuid.uuid4()),
                        original=result.text,
                        translated=result.text,  # Placeholder — translation module fills this
                        is_sentence_end=result.is_final,
                        confidence=result.confidence,
                        latency_ms=0,
                        timestamp=result.timestamp,
                    ).model_dump()
                )
    except Exception as e:
        logger.error(f"ASR processing error [{session_id}]: {e}")


# ── Main WebSocket endpoint ──────────────────────────────────────

@router.websocket("/ws/translate")
async def translate_websocket(websocket: WebSocket):
    """
    Main translation WebSocket endpoint.

    Client → Server:
      Binary: 16-bit PCM audio, 16kHz, mono, ~200ms chunks
      Text (JSON): {"type": "start"|"pause"|"resume"|"stop"|"update_glossary"|"ping", ...}

    Server → Client (JSON):
      subtitle_draft  — ASR result in progress
      subtitle_final  — finalized sentence
      status          — pipeline status + metrics
      error           — error with recovery info
      pong            — heartbeat response
    """
    now = time.time()

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

    await websocket.accept()
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
        _remove_handler(session_id)
        sessions.remove(session_id)
        manager.disconnect(session_id)
        elapsed = time.time() - now
        logger.info(f"Session [{session_id}] cleaned up (duration: {elapsed:.1f}s, active: {sessions.active_count})")
