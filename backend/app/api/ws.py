"""
WebSocket API routes.

The /ws/translate endpoint is the main pipeline for real-time translation:
  - Client sends binary PCM audio chunks + JSON control messages
  - Server sends subtitle JSON (draft → corrected → final) + status + errors

Pipeline:  PCM bytes → float32 → VAD → ASR → LLM translate → subtitle_draft → client

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
from ..engines.translation.context_manager import TranslationContext
from ..engines.correction.corrector import LLMCorrector, LLMConfig
from ..engines.asr.cloud_asr import AsrEngineConfig, create_cloud_asr, StreamingASR
from ..engines.asr.audio_capture import get_audio_capture
from ..engines.asr.ring_buffer import RingBuffer
from ..engines.asr.mark_processor import MarkGenerator, Mark, MarkType
from ..engines.asr.transcription_worker import TranscriptionWorker

router = APIRouter()


# ── Sentence accumulator — shared by mic and system audio paths ──

class SentenceAccumulator:
    """Accumulates ASR text revisions and detects sentence boundaries.

    Mirrors the system audio _cloud_asr_loop logic:
      - Non-final revisions update `current_text` (frontend shows as "in-progress")
      - Punctuation or timeout triggers `commit()` → final sentence + translate
      - Each committed sentence gets a stable `sequence_id`
    """

    _SENT_END = set('.!?。？！…')
    _MIN_LEN = 15
    _TIMEOUT_S = 10.0

    def __init__(self):
        self.cur_text = ''
        self.cur_id = 's0'
        self.sent_num = 0
        self.last_time = time.time()

    def update(self, new_text: str):
        """Feed a new ASR revision. Returns list of (action, ...) tuples."""
        actions = []
        if not new_text or new_text == self.cur_text:
            return actions

        old_text = self.cur_text

        # Timeout → commit current
        if old_text and (time.time() - self.last_time > self._TIMEOUT_S) and len(old_text.strip()) >= self._MIN_LEN:
            sid = self._commit(old_text.strip())
            actions.append(('commit', sid, old_text.strip()))
            old_text = ''

        # Revision: ASR changed earlier words
        if old_text and not new_text.startswith(old_text):
            if self._has_end_punct(new_text) and len(new_text.strip()) >= self._MIN_LEN:
                pi = self._last_punct_pos(new_text)
                sent = new_text[:pi + 1].strip()
                sid = self._commit(sent)
                actions.append(('commit', sid, sent))
                remainder = new_text[pi + 1:].strip()
                self.cur_text = remainder
                self.last_time = time.time()
                actions.append(('draft', self.cur_id, remainder))
                return actions
            elif len(old_text.strip()) >= self._MIN_LEN and len(new_text.strip()) < len(old_text.strip()) - 5:
                sid = self._commit(old_text.strip())
                actions.append(('commit', sid, old_text.strip()))
                self.cur_text = new_text
                self.last_time = time.time()
                actions.append(('draft', self.cur_id, new_text))
                return actions
            else:
                self.cur_text = new_text
                self.last_time = time.time()
                actions.append(('draft', self.cur_id, new_text))
                return actions

        # Text shrank
        if len(new_text) < len(old_text):
            self.cur_text = new_text
            self.last_time = time.time()
            actions.append(('draft', self.cur_id, new_text))
            return actions

        # Text grew
        self.cur_text = new_text
        self.last_time = time.time()

        if self._has_end_punct(new_text) and len(new_text.strip()) >= self._MIN_LEN:
            pi = self._last_punct_pos(new_text)
            sent = new_text[:pi + 1].strip()
            sid = self._commit(sent)
            actions.append(('commit', sid, sent))
            remainder = new_text[pi + 1:].strip()
            if remainder:
                self.cur_text = remainder
                actions.append(('draft', self.cur_id, remainder))
        else:
            actions.append(('draft', self.cur_id, new_text))

        return actions

    def _commit(self, sentence: str) -> str:
        sid = self.cur_id
        self.sent_num += 1
        self.cur_id = f's{self.sent_num}'
        self.cur_text = ''
        self.last_time = time.time()
        logger.info(f"[ACCUM] commit [{sid}] '{sentence[:60]}' (total={self.sent_num})")
        return sid

    @classmethod
    def _has_end_punct(cls, text: str) -> bool:
        t = text.rstrip()
        return bool(t) and t[-1] in cls._SENT_END

    @classmethod
    def _last_punct_pos(cls, text: str) -> int:
        return max(text.rfind(c) for c in cls._SENT_END)


# ── Per-session state ───────────────────────────────────────────

_session_contexts: dict[str, TranslationContext] = {}
_session_llm_configs: dict[str, LLMConfig] = {}
_session_cloud_asr: dict[str, StreamingASR] = {}
_session_asr_configs: dict[str, AsrEngineConfig] = {}
_session_systems: dict[str, tuple[RingBuffer, MarkGenerator, TranscriptionWorker]] = {}
_session_accumulators: dict[str, SentenceAccumulator] = {}


def _get_context(session_id: str, create: bool = False) -> TranslationContext | None:
    if session_id not in _session_contexts and create:
        _session_contexts[session_id] = TranslationContext()
    return _session_contexts.get(session_id)


def _cleanup_session(session_id: str) -> None:
    """Stop system capture, worker, generator, and remove session state."""
    system = _session_systems.pop(session_id, None)
    if system:
        _, gen, worker = system
        if gen:
            gen.stop()
        if worker:
            worker.stop()
    _session_contexts.pop(session_id, None)
    _session_llm_configs.pop(session_id, None)
    _session_cloud_asr.pop(session_id, None)
    _session_asr_configs.pop(session_id, None)
    _session_accumulators.pop(session_id, None)
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
                async def _do_translate(sid: str, full_text: str):
                    """Translate full_text via LLM and send result with sid."""
                    try:
                        s = sessions.get(session_id)
                        if s and s.state != SessionState.LISTENING:
                            return
                        llm_cfg = _session_llm_configs.get(session_id)
                        if not (llm_cfg and llm_cfg.enabled and llm_cfg.api_key):
                            logger.warning(f"[DBG-TX] _do_translate: LLM未配置，跳过翻译 sid={sid[:6]}")
                            return
                        from ..engines.correction.corrector import LLMCorrector
                        corrector = LLMCorrector(llm_cfg)
                        src_l = (s.config.source_lang if s else "EN").upper()
                        tgt_l = (s.config.target_lang if s else "ZH").upper()
                        prompt = f"Translate {src_l} to {tgt_l}:\n\n{full_text}\n\n{tgt_l}:"
                        result = await corrector._call_llm(prompt)
                        translated = result.strip() or full_text
                        logger.info(f"[DBG-TX] _do_translate(LLM): sid={sid[:6]} '{full_text[:40]}' → '{translated[:40]}'")
                        s = sessions.get(session_id)
                        if s and s.state != SessionState.LISTENING:
                            return
                        logger.info(f"[DBG-TX] → send_json subtitle_draft: sid={sid[:6]} is_replace=True orig='{full_text[:40]}' trans='{translated[:40]}'")
                        await ws.send_json(SubtitleDraft(
                            sequence_id=sid, original=full_text, translated=translated,
                            is_sentence_end=True, is_replace=True,
                            timestamp=time.time()
                        ).model_dump())
                    except Exception as e:
                        logger.error(f"[CloudTX] translate error: {e}")

                _cloud_pcm_queue: asyncio.Queue = asyncio.Queue()

                async def _cloud_asr_loop():
                    """ASR -> accumulate -> split at punctuation -> push to frontend."""
                    _SENT_END = set('.!?。？！…')
                    _MIN_LEN = 15
                    _TIMEOUT = 10
                    logger.info('[CloudASR:sys] loop started')

                    # Backend buffer: completed sentences
                    history = []
                    cur_text = ''
                    cur_id = 's0'
                    sent_num = 0
                    last_time = time.time()

                    def _send(text, sid, is_final):
                        logger.info(f"[DBG-TX] _send(ASR): sid={sid} final={is_final} text='{text[:60]}'")
                        return SubtitleDraft(
                            sequence_id=sid, original=text, translated='',
                            is_sentence_end=is_final, is_replace=False,
                            timestamp=time.time()
                        )

                    def _commit(sentence):
                        nonlocal cur_text, cur_id, sent_num, last_time
                        sid = cur_id
                        history.append(sentence)
                        sent_num += 1
                        cur_id = f's{sent_num}'
                        cur_text = ''
                        last_time = time.time()
                        logger.info(f"[COMMIT] [{sid}] '{sentence[:60]}' (history={len(history)})")
                        return sid

                    def _has_end_punct(text):
                        t = text.rstrip()
                        return t and t[-1] in _SENT_END

                    def _last_punct_pos(text):
                        return max(text.rfind(c) for c in _SENT_END)

                    while True:
                        pcm = await _cloud_pcm_queue.get()
                        if pcm is None:
                            break

                        # Reset on pause
                        try:
                            s = sessions.get(session_id)
                            if s and s.state != SessionState.LISTENING:
                                while True:
                                    try: _cloud_pcm_queue.get_nowait()
                                    except asyncio.QueueEmpty: break
                                cur_text = ''
                                sent_num += 1
                                cur_id = f's{sent_num}'
                                continue
                        except Exception:
                            pass

                        # Drain batch
                        chunks = [pcm]
                        while True:
                            try: chunks.append(_cloud_pcm_queue.get_nowait())
                            except asyncio.QueueEmpty: break

                        try:
                            combined = b''.join(chunks)
                            async for result in cloud_asr.process_chunk(combined):
                                new_text = result.text
                                if not new_text or new_text == cur_text:
                                    continue
                                logger.info(f"[ASR] text='{new_text[:60]}' len={len(new_text)} cur_len={len(cur_text)}")

                                s = sessions.get(session_id)
                                if not s or s.state != SessionState.LISTENING:
                                    continue

                                # Timeout -> commit current
                                if cur_text and time.time() - last_time > _TIMEOUT and len(cur_text.strip()) >= _MIN_LEN:
                                    sid = _commit(cur_text.strip())
                                    await ws.send_json(_send(history[-1], sid, True).model_dump())
                                    asyncio.ensure_future(_do_translate(sid, history[-1]))

                                # Revision: ASR changed earlier words
                                if cur_text and not new_text.startswith(cur_text):
                                    if _has_end_punct(new_text) and len(new_text.strip()) >= _MIN_LEN:
                                        # Has punctuation → split
                                        pi = _last_punct_pos(new_text)
                                        sent = new_text[:pi + 1].strip()
                                        sid = _commit(sent)
                                        await ws.send_json(_send(history[-1], sid, True).model_dump())
                                        asyncio.ensure_future(_do_translate(sid, history[-1]))
                                        remainder = new_text[pi + 1:].strip()
                                        if remainder:
                                            cur_text = remainder
                                            await ws.send_json(_send(remainder, cur_id, False).model_dump())
                                    elif len(cur_text.strip()) >= _MIN_LEN and len(new_text.strip()) < len(cur_text.strip()) - 5:
                                        # ASR jumped to shorter text → old sentence is done
                                        logger.info(f"[JUMP] cur='{cur_text[:40]}' new='{new_text[:40]}'")
                                        sid = _commit(cur_text.strip())
                                        await ws.send_json(_send(history[-1], sid, True).model_dump())
                                        asyncio.ensure_future(_do_translate(sid, history[-1]))
                                        cur_text = new_text
                                        last_time = time.time()
                                        await ws.send_json(_send(new_text, cur_id, False).model_dump())
                                    else:
                                        cur_text = new_text
                                        last_time = time.time()
                                        await ws.send_json(_send(new_text, cur_id, False).model_dump())
                                    continue

                                # Text shrank
                                if len(new_text) < len(cur_text):
                                    cur_text = new_text
                                    last_time = time.time()
                                    await ws.send_json(_send(new_text, cur_id, False).model_dump())
                                    continue

                                # Text grew
                                cur_text = new_text
                                last_time = time.time()

                                if _has_end_punct(new_text) and len(new_text.strip()) >= _MIN_LEN:
                                    pi = _last_punct_pos(new_text)
                                    sent = new_text[:pi + 1].strip()
                                    sid = _commit(sent)
                                    await ws.send_json(_send(history[-1], sid, True).model_dump())
                                    asyncio.ensure_future(_do_translate(sid, history[-1]))
                                    remainder = new_text[pi + 1:].strip()
                                    if remainder:
                                        cur_text = remainder
                                        await ws.send_json(_send(remainder, cur_id, False).model_dump())
                                else:
                                    await ws.send_json(_send(new_text, cur_id, False).model_dump())
                        except Exception as e:
                            logger.error(f'[CloudASR:sys] error: {e}')
                    logger.info('[CloudASR:sys] loop ended')

                _cloud_asr_task = asyncio.ensure_future(_cloud_asr_loop())

                def _on_cloud_pcm(pcm: bytes):
                    loop = asyncio.get_event_loop()
                    loop.call_soon_threadsafe(_cloud_pcm_queue.put_nowait, pcm)

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
                        logger.warning(f"[TX] LLM未配置，返回原文")
                        translated = original
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
            if gen:
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
            if gen:
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
    """Process audio chunk through ASR + LLM pipeline."""
    _n = getattr(_process_audio_chunk, '_n', 0) + 1
    _process_audio_chunk._n = _n

    try:
        session = sessions.require(session_id)
    except KeyError:
        if _n <= 3: logger.error("[DBG-TRACK] ③后端收到 WS bytes — 但 NO SESSION")
        return

    if session.state != SessionState.LISTENING:
        if _n <= 3: logger.warning(f"[DBG-TRACK] ③后端收到 WS bytes — 但 state={session.state} (非 LISTENING)")
        return

    if _n <= 10 or _n % 50 == 0:
        logger.info(f"[DBG-TRACK] ③后端收到 WS #{_n}: {len(data)}B, state={session.state}")

    sessions.record_audio_chunk(session_id)

    cloud_asr = _session_cloud_asr.get(session_id)
    if cloud_asr:
        try:
            logger.info(f"[DBG-TRACK] ④走云端ASR分支, pcm={len(data)}B")
            # Get or create per-session accumulator
            accum = _session_accumulators.get(session_id)
            if accum is None:
                accum = SentenceAccumulator()
                _session_accumulators[session_id] = accum

            async for asr_result in cloud_asr.process_chunk(data):
                logger.info(f"[DBG-TRACK] ⑤云端ASR结果: text='{asr_result.text}' is_final={asr_result.is_final}")
                if not asr_result.text:
                    continue

                # Feed into accumulator — handles dedup, revision, sentence boundary
                actions = accum.update(asr_result.text)

                for action in actions:
                    kind = action[0]

                    if kind == 'draft':
                        # In-progress revision: update "current" line on frontend
                        _, sid, text = action
                        logger.info(f"[DBG-TX] mic draft: sid={sid} text='{text[:50]}'")
                        await ws.send_json(
                            SubtitleDraft(sequence_id=sid, original=text, translated="",
                                          is_sentence_end=False, timestamp=time.time()).model_dump()
                        )

                    elif kind == 'commit':
                        # Sentence committed: add to history + translate
                        _, sid, text = action
                        sessions.record_sentence(session_id)
                        logger.info(f"[DBG-TX] mic commit: sid={sid} text='{text[:50]}'")
                        # Send final ASR result
                        await ws.send_json(
                            SubtitleDraft(sequence_id=sid, original=text, translated="",
                                          is_sentence_end=True, timestamp=time.time()).model_dump()
                        )
                        # Translate via LLM
                        async def _bg_translate(_sid=sid, _text=text):
                            try:
                                s = sessions.get(session_id)
                                llm_cfg = _session_llm_configs.get(session_id)
                                if not (llm_cfg and llm_cfg.enabled and llm_cfg.api_key):
                                    logger.warning(f"[DBG-TX] mic翻译: LLM未配置，跳过 sid={_sid[:6]}")
                                    return
                                from ..engines.correction.corrector import LLMCorrector
                                corrector = LLMCorrector(llm_cfg)
                                src_l = (s.config.source_lang if s else "EN").upper()
                                tgt_l = (s.config.target_lang if s else "ZH").upper()
                                prompt = f"Translate {src_l} to {tgt_l}:\n\n{_text}\n\n{tgt_l}:"
                                result = await corrector._call_llm(prompt)
                                translated = result.strip() or _text
                                logger.info(f"[DBG-TX] mic翻译(LLM): sid={_sid[:6]} '{_text[:40]}' → '{translated[:40]}'")
                                await ws.send_json(
                                    SubtitleDraft(sequence_id=_sid, original=_text, translated=translated,
                                                  is_sentence_end=True, is_replace=True,
                                                  timestamp=time.time()).model_dump()
                                )
                            except Exception as e:
                                logger.error(f"[DBG-TX] mic翻译异常: {e}")
                        asyncio.ensure_future(_bg_translate())

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
        logger.info(f"[DBG-TRACK] ④走本地ASR分支 (StreamHandler 新建)")
    handler = handlers.get(session_id)
    if not handler:
        return

    try:
        async for asr_result in handler.process_chunk(data):
            if asr_result.text:
                logger.info(f"[DBG-TRACK] ⑤本地ASR结果: text='{asr_result.text}' is_final={asr_result.is_final}")
                sessions.record_sentence(session_id)

                # Translation via LLM
                s = sessions.get(session_id)
                glossary = [t.model_dump() for t in s.config.glossary_terms] if s else []
                llm_cfg = _session_llm_configs.get(session_id)
                tx_backend = "llm"
                latency_ms = 0
                if llm_cfg and llm_cfg.enabled and llm_cfg.api_key:
                    from ..engines.correction.corrector import LLMCorrector
                    corrector = LLMCorrector(llm_cfg)
                    src = sessions.get(session_id).config.source_lang if session_id else "EN".upper() if session and session.config else 'EN'
                    tgt = sessions.get(session_id).config.target_lang if session_id else "ZH".upper() if session and session.config else 'ZH'
                    prompt = f"""Translate the following {src} text to {tgt}.

{src}: {asr_result.text}

{tgt}:"""
                    result = await corrector._call_llm(prompt)
                    translated_text = result.strip() or asr_result.text
                else:
                    logger.warning(f"[DBG-TX] 本地ASR: LLM未配置，返回原文")
                    translated_text = asr_result.text
                    tx_backend = "none"

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
                logger.info(f"[DBG-TRACK] ⑥翻译完成: \"{asr_result.text[:50]}\" → \"{translated_text[:50]}\" backend={tx_backend}")
                logger.info(f"[SEND] subtitle_draft: \"{asr_result.text[:50]}\" → \"{translated_text[:50]}\"")
                await ws.send_json(
                    SubtitleDraft(
                        sequence_id=seq_id,
                        original=asr_result.text,
                        translated=translated_text,
                        is_sentence_end=asr_result.is_final,
                        confidence=asr_result.confidence,
                        latency_ms=round(latency_ms),
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
            if gen:
                await gen.drain()
                await asyncio.sleep(1)  # Let worker process the drain mark
        _cleanup_session(session_id)
        sessions.remove(session_id)
        manager.disconnect(session_id)
        elapsed = time.time() - now
        logger.info(f"Session [{session_id}] cleaned up (duration: {elapsed:.1f}s, active: {sessions.active_count})")
