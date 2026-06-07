"""
WebSocket API routes.

The /ws/translate endpoint is the main pipeline for real-time translation:
  - Client sends binary PCM audio chunks + JSON control messages
  - Server sends subtitle JSON (draft → corrected → final) + status + errors

Pipeline:  PCM bytes → float32 → VAD → ASR → NMT → subtitle_draft → client
                                                  └→ LLM correct → subtitle_corrected (async)

Protocol frames are defined in models/subtitle.py and models/session.py.
"""
import asyncio
import json
import time
import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from ..core.connection_manager import manager
from ..core.session_manager import sessions, SessionState, SessionConfig
from ..models.subtitle import (
    StatusMessage, ErrorMessage, SubtitleDraft, SubtitleFinal, SubtitleCorrected,
)
from ..models.glossary import Term
from ..engines.translation.nmt_engine import get_nmt_engine
from ..engines.translation.context_manager import TranslationContext
from ..engines.correction.corrector import LLMCorrector, LLMConfig
from ..engines.asr.cloud_asr import AsrEngineConfig, create_cloud_asr, StreamingASR
from ..engines.asr.audio_capture import get_audio_capture
from ..engines.asr.ring_buffer import RingBuffer
from ..engines.asr.mark_processor import MarkGenerator, Mark, MarkType
from ..engines.asr.transcription_worker import TranscriptionWorker

router = APIRouter()

# ── Per-session state ───────────────────────────────────────────

_session_contexts: dict[str, TranslationContext] = {}
_session_llm_configs: dict[str, LLMConfig] = {}
_session_cloud_asr: dict[str, StreamingASR] = {}
_session_asr_configs: dict[str, AsrEngineConfig] = {}
_session_systems: dict[str, tuple[RingBuffer, MarkGenerator, TranscriptionWorker]] = {}


def _get_context(session_id: str, create: bool = False) -> TranslationContext | None:
    if session_id not in _session_contexts and create:
        _session_contexts[session_id] = TranslationContext()
    return _session_contexts.get(session_id)


def _cleanup_session(session_id: str) -> None:
    """Stop system capture, worker, generator, and remove session state."""
    system = _session_systems.pop(session_id, None)
    if system:
        _, gen, worker = system
        gen.stop()
        worker.stop()
    _session_contexts.pop(session_id, None)
    _session_llm_configs.pop(session_id, None)
    _session_cloud_asr.pop(session_id, None)
    _session_asr_configs.pop(session_id, None)
    try: get_audio_capture().stop()
    except: pass


async def _run_correction(
    ws: WebSocket,
    session_id: str,
    original: str,
    draft: str,
    seq_id: str,
    context: list[tuple[str, str]],
) -> None:
    """Run LLM correction in background and send result back."""
    try:
        llm_config = _session_llm_configs.get(session_id)
        if not llm_config:
            return

        corrector = LLMCorrector(llm_config)
        sess = sessions.get(session_id)
        glossary = [t.model_dump() for t in sess.config.glossary_terms] if sess else []
        result = await corrector.correct(original, draft, context, glossary_terms=glossary)

        if result.corrected and result.corrected != draft:
            try:
                await ws.send_json(
                    SubtitleCorrected(
                        sequence_id=seq_id,
                        corrected_text=result.corrected,
                        diff=result.diff_segments,
                        latency_ms=result.latency_ms,
                        timestamp=time.time(),
                    ).model_dump()
                )
            except Exception:
                pass  # WebSocket may have closed
    except Exception as e:
        logger.warning(f"LLM correction failed [{session_id}]: {e}")


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

    # Initialize translation context
    _get_context(session_id, create=True)

    # Parse ASR config from frontend
    asr_raw = config.get("asr", {})
    asr_config = AsrEngineConfig(
        provider=asr_raw.get("provider", "local"),
        api_key=asr_raw.get("apiKey", ""),
        api_secret=asr_raw.get("apiSecret", ""),
        app_id=asr_raw.get("appId", ""),
        base_url=asr_raw.get("baseUrl", ""),
    )
    _session_asr_configs[session_id] = asr_config
    if asr_config.provider != "local" and (asr_config.api_key or asr_config.app_id):
        try:
            _session_cloud_asr[session_id] = create_cloud_asr(asr_config)
            logger.info(f"Session [{session_id}] using cloud ASR: {asr_config.provider}")
        except Exception as e:
            logger.warning(f"Cloud ASR init failed: {e}")

    # Parse LLM config from frontend
    llm_raw = config.get("llm", {})
    _session_llm_configs[session_id] = LLMConfig(
        provider=llm_raw.get("provider", "openai"),
        api_key=llm_raw.get("apiKey", ""),
        model=llm_raw.get("model", "gpt-4o-mini"),
        base_url=llm_raw.get("baseUrl", ""),
        enabled=llm_raw.get("enabled", False),
    )

    # Start system audio capture if audio_source is 'system'
    cloud_asr = _session_cloud_asr.get(session_id)

    if session_config.audio_source == 'system':
        try:
            import numpy as np
            # Cloud ASR path: feed PCM directly, no local SenseVoice
            if cloud_asr:
                async def _cloud_tx(text: str):
                    s = sessions.get(session_id)
                    nmt = get_nmt_engine()
                    t = await nmt.translate(text)
                    seq_id = str(uuid.uuid4())
                    await ws.send_json(SubtitleDraft(sequence_id=seq_id, original=text, translated=t.text, is_sentence_end=True, timestamp=time.time()).model_dump())

                def _on_cloud_pcm(pcm: bytes):
                    async def _process():
                        async for result in cloud_asr.process_chunk(pcm):
                            logger.info(f"[CloudASR:sys] text='{result.text}' is_final={result.is_final}")
                            if result.text:
                                await _cloud_tx(result.text)
                    asyncio.create_task(_process())

                cap = get_audio_capture()
                cap.start(_on_cloud_pcm)
                _session_systems[session_id] = (None, None, None)  # placeholder for cleanup
                logger.info(f"Session [{session_id}] system capture → cloud ASR ({asr_config.provider})")
            else:
                # Local ASR path: RingBuffer + MarkGenerator + TranscriptionWorker
                from ..engines.asr.ring_buffer import RingBuffer
                from ..engines.asr.mark_processor import MarkGenerator
                from ..engines.asr.transcription_worker import TranscriptionWorker
                ring = RingBuffer()
                gen = MarkGenerator(ring)
                async def _tx(original: str, duration: float):
                    logger.info(f"[TX] \"{original[:60]}\" ({duration:.1f}s)")
                    s = sessions.get(session_id)
                    glossary = [t.model_dump() for t in s.config.glossary_terms] if s else []
                    llm_cfg = _session_llm_configs.get(session_id)
                    if llm_cfg and llm_cfg.enabled and llm_cfg.api_key:
                        from ..engines.correction.corrector import LLMCorrector
                        try:
                            corrector = LLMCorrector(llm_cfg)
                            s = sessions.get(session_id)
                            src_l = (s.config.source_lang if s else "EN").upper()
                            tgt_l = (s.config.target_lang if s else "ZH").upper()
                            prompt = f"Translate {src_l} to {tgt_l}:\n\n{original}\n\n{tgt_l}:"
                            result = await corrector._call_llm(prompt)
                            translated = result.strip() or original
                        except Exception:
                            translated = original
                    else:
                        nmt = get_nmt_engine()
                        t = await nmt.translate(original)
                        translated = t.text
                    seq_id = str(uuid.uuid4())
                    ctx = _get_context(session_id)
                    if ctx and translated:
                        ctx.add(source=original, target=translated, sequence_id=seq_id, timestamp=time.time())
                    await ws.send_json(SubtitleDraft(sequence_id=seq_id, original=original, translated=translated, is_sentence_end=True, timestamp=time.time()).model_dump())
                worker = TranscriptionWorker(ring, gen.queue, _tx)
                cap = get_audio_capture()
                cap.start(lambda pcm: ring.write(np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0))
                gen.start(); worker.start()
                asyncio.create_task(gen.run()); asyncio.create_task(worker.run())
                _session_systems[session_id] = (ring, gen, worker)
                logger.info(f"Session [{session_id}] system capture started (RingBuffer+Worker)")
        except Exception as e:
            logger.warning(f"System capture failed: {e}")

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
    """Handle stop — drain remaining audio and clean up."""
    try:
        # Drain ring buffer
        system = _session_systems.get(session_id)
        if system:
            _, gen, _ = system
            await gen.drain()
            await asyncio.sleep(1.5)  # Let worker process drain

        session = sessions.get(session_id)
        if session:
            await ws.send_json(
                StatusMessage(
                    status="idle",
                    message=f"Session ended: {session.total_sentences} sentences, {session.total_audio_chunks} chunks",
                ).model_dump()
            )

        cloud_asr = _session_cloud_asr.get(session_id)
        if cloud_asr:
            try: await cloud_asr.close()
            except: pass
        # Drain: flush remaining audio before cleanup
        system = _session_systems.get(session_id)
        if system:
            _, gen, _ = system
            await gen.drain()
            await asyncio.sleep(1)  # Let worker process the drain mark
        _cleanup_session(session_id)
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
    """Process audio chunk through ASR + NMT pipeline."""
    _n = getattr(_process_audio_chunk, '_n', 0) + 1
    _process_audio_chunk._n = _n

    try:
        session = sessions.require(session_id)
    except KeyError:
        if _n <= 3: logger.error("[AUDIO] NO SESSION")
        return

    if session.state != SessionState.LISTENING:
        if _n <= 3: logger.warning(f"[AUDIO] Wrong state: {session.state}")
        return

    if _n <= 5:
        logger.info(f"[AUDIO] #{_n}: {len(data)}B, state={session.state}")

    sessions.record_audio_chunk(session_id)

    cloud_asr = _session_cloud_asr.get(session_id)
    if cloud_asr:
        try:
            async for asr_result in cloud_asr.process_chunk(data):
                logger.info(f"[CloudASR] session={session_id} text='{asr_result.text}' is_final={asr_result.is_final}")
                if asr_result.text:
                    sessions.record_sentence(session_id)
                    nmt_engine = get_nmt_engine()
                    translation = await nmt_engine.translate(asr_result.text)
                    logger.info(f"[CloudASR] translated='{translation.text}' latency={translation.latency_ms}ms")
                    seq_id = str(uuid.uuid4())
                    ctx = _get_context(session_id)
                    if ctx and translation.text:
                        ctx.add(source=asr_result.text, target=translation.text, sequence_id=seq_id, timestamp=time.time())
                    await ws.send_json(
                        SubtitleDraft(sequence_id=seq_id, original=asr_result.text, translated=translation.text,
                                      is_sentence_end=asr_result.is_final, confidence=asr_result.confidence,
                                      latency_ms=round(translation.latency_ms), timestamp=asr_result.timestamp).model_dump()
                    )
        except Exception as e:
            logger.warning(f"Cloud ASR error [{session_id}]: {e}", exc_info=True)
        return

    # Mic mode: not using ring buffer system
    from ..engines.asr.stream_handler import StreamHandler
    if session_id not in getattr(_process_audio_chunk, '_handlers', {}):
        setattr(_process_audio_chunk, '_handlers', {})
    handlers = getattr(_process_audio_chunk, '_handlers', {})
    if session_id not in handlers:
        handlers[session_id] = StreamHandler()
    handler = handlers.get(session_id)
    if not handler:
        return

    try:
        async for asr_result in handler.process_chunk(data):
            if asr_result.text:
                sessions.record_sentence(session_id)

                # Translation: LLM if enabled, else NMT
                s = sessions.get(session_id)
                glossary = [t.model_dump() for t in s.config.glossary_terms] if s else []
                llm_cfg = _session_llm_configs.get(session_id)
                if llm_cfg and llm_cfg.enabled and llm_cfg.api_key:
                    from ..engines.correction.corrector import LLMCorrector
                    corrector = LLMCorrector(llm_cfg)
                    # Use LLM for full translation (not just correction)
                    src = sessions.get(session_id).config.source_lang if session_id else "EN".upper() if session and session.config else 'EN'
                    tgt = sessions.get(session_id).config.target_lang if session_id else "ZH".upper() if session and session.config else 'ZH'
                    prompt = f"""Translate the following {src} text to {tgt}.

{src}: {asr_result.text}

{tgt}:"""
                    result = await corrector._call_llm(prompt)
                    translated_text = result.strip() or asr_result.text
                    nmt_latency = 0
                else:
                    nmt_engine = get_nmt_engine()
                    translation = await nmt_engine.translate(asr_result.text)
                    translated_text = translation.text
                    nmt_latency = translation.latency_ms

                # Store context for future LLM correction
                seq_id = str(uuid.uuid4())
                ctx = _get_context(session_id)
                if ctx and translated_text:
                    ctx.add(
                        source=asr_result.text,
                        target=translated_text,
                        sequence_id=seq_id,
                        timestamp=time.time(),
                    )

                # Send draft to client
                logger.info(f"[SEND] subtitle_draft: \"{asr_result.text[:50]}\" → \"{translated_text[:50]}\"")
                await ws.send_json(
                    SubtitleDraft(
                        sequence_id=seq_id,
                        original=asr_result.text,
                        translated=translated_text,
                        is_sentence_end=asr_result.is_final,
                        confidence=asr_result.confidence,
                        latency_ms=round(nmt_latency),
                        timestamp=asr_result.timestamp,
                    ).model_dump()
                )

                # Async LLM correction (fire and forget)
                llm_config = _session_llm_configs.get(session_id)
                if llm_config and llm_config.enabled and llm_config.api_key:
                    ctx = _get_context(session_id)
                    context_pairs = [(e.source, e.target) for e in (ctx.get_recent(4) if ctx else [])]
                    asyncio.create_task(
                        _run_correction(
                            ws=ws,
                            session_id=session_id,
                            original=asr_result.text,
                            draft=translated_text,
                            seq_id=seq_id,
                            context=context_pairs,
                        )
                    )

    except Exception as e:
        if "Cannot call" in str(e):
            raise  # WS died, let main loop break
        logger.warning(f"Audio processing error [{session_id}]: {e}")


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
        sys_active = _session_systems.get(session_id)

        while True:
            if sys_active:
                # RingBuffer mode: worker handles transcription, just poll WS
                try:
                    data = await asyncio.wait_for(websocket.receive(), timeout=1.0)
                    if "text" in data:
                        await _process_control_message(session_id, websocket, data["text"])
                        sys_active = _session_systems.get(session_id)
                except asyncio.TimeoutError:
                    pass
            else:
                data = await websocket.receive()
                if "text" in data:
                    await _process_control_message(session_id, websocket, data["text"])
                elif "bytes" in data:
                    await _process_audio_chunk(session_id, websocket, data["bytes"])
                sys_active = _session_systems.get(session_id)

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
        cloud_asr = _session_cloud_asr.get(session_id)
        if cloud_asr:
            try: await cloud_asr.close()
            except: pass
        # Drain: flush remaining audio before cleanup
        system = _session_systems.get(session_id)
        if system:
            _, gen, _ = system
            await gen.drain()
            await asyncio.sleep(1)  # Let worker process the drain mark
        _cleanup_session(session_id)
        sessions.remove(session_id)
        manager.disconnect(session_id)
        elapsed = time.time() - now
        logger.info(f"Session [{session_id}] cleaned up (duration: {elapsed:.1f}s, active: {sessions.active_count})")
