"""
ASR Stream Handler — VAD-based sentence boundary detection.

Uses VAD to detect natural speech pauses instead of fixed-time batch windows.
When silence exceeds 0.6s, the accumulated speech is transcribed as a sentence.
"""
import asyncio
from typing import AsyncGenerator, Optional
import numpy as np
from loguru import logger
from .sherpa_engine import SherpaASREngine, ASRResult, get_asr_engine
from .vad_processor import VadProcessor, get_vad_processor

TARGET_RATE = 16000
SILENCE_THRESHOLD = 0.6     # Sentence boundary on silence
MIN_SPEECH_DURATION = 0.5   # Minimum speech to transcribe
PERIODIC_FLUSH = 3.0        # Force flush every 3s even without silence
MAX_SPEECH_DURATION = 12.0  # Hard cap


class StreamHandler:
    """Per-session handler: VAD detects sentence boundaries → batch transcribe."""

    def __init__(self) -> None:
        self._engine = get_asr_engine()
        self._vad = get_vad_processor()

        # Speech accumulation
        self._speech_buffer: list[np.ndarray] = []
        self._speech_duration: float = 0.0

        # VAD state tracking
        self._in_speech: bool = False          # Currently in a speech segment
        self._silence_duration: float = 0.0    # Accumulated silence since last speech
        self._total_chunks: int = 0

        # Deduplication
        self._prev_text: str = ""

    async def process_chunk(self, pcm_bytes: bytes) -> AsyncGenerator[ASRResult, None]:
        if len(pcm_bytes) == 0:
            logger.warning("[DBG-TRACK] StreamHandler: 收到空 pcm_bytes")
            return

        try:
            samples = self._bytes_to_float32(pcm_bytes)
        except Exception as e:
            logger.warning(f"[DBG-TRACK] StreamHandler: bytes→float32 失败: {e}")
            return

        self._total_chunks += 1
        if self._total_chunks <= 10 or self._total_chunks % 50 == 0:
            rms = float(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))
            logger.info(f"[DBG-TRACK] ④本地ASR chunk #{self._total_chunks}: {len(pcm_bytes)}B, {len(samples)}samples, rms={rms:.5f}")

        has_speech = self._vad.process(samples)

        if has_speech:
            # Speech detected → accumulate, reset silence counter
            self._in_speech = True
            self._silence_duration = 0.0
            self._speech_buffer.append(samples)
            self._speech_duration += len(samples) / TARGET_RATE

            # Periodic flush: keep content flowing even without silence
            if self._speech_duration >= PERIODIC_FLUSH:
                async for r in self._flush():
                    yield r
            elif self._speech_duration >= MAX_SPEECH_DURATION:
                async for r in self._flush():
                    yield r

        elif self._in_speech:
            # Silence during speech → accumulate silence counter
            self._silence_duration += len(samples) / TARGET_RATE
            self._speech_buffer.append(samples)  # Keep silence samples for context
            self._speech_duration += len(samples) / TARGET_RATE

            # Sentence boundary detected
            if self._silence_duration >= SILENCE_THRESHOLD:
                async for r in self._flush():
                    yield r
                self._in_speech = False
                self._silence_duration = 0.0
                self._speech_duration = 0.0

        # else: silence outside speech → do nothing

    async def _flush(self) -> AsyncGenerator[ASRResult, None]:
        """Transcribe accumulated speech as a sentence."""
        if not self._speech_buffer or self._speech_duration < MIN_SPEECH_DURATION:
            logger.info(f"[DBG-TRACK] ⑤flush跳过: buffer={len(self._speech_buffer)} chunks, duration={self._speech_duration:.2f}s < {MIN_SPEECH_DURATION}s")
            self._speech_buffer.clear()
            self._speech_duration = 0.0
            return

        audio = np.concatenate(self._speech_buffer)
        buf_chunks = len(self._speech_buffer)
        self._speech_buffer.clear()
        self._speech_duration = 0.0

        logger.info(f"[DBG-TRACK] ⑤flush转写: {buf_chunks} chunks, {len(audio)} samples ({len(audio)/TARGET_RATE:.1f}s)")
        result = await asyncio.to_thread(self._engine.transcribe, audio)
        logger.info(f"[DBG-TRACK] ⑤ASR转写结果: text='{result.text}' engine_mode={self._engine.mode}")
        if result.text and result.text != self._prev_text:
            self._prev_text = result.text
            logger.info(f"[SENTENCE] {self._speech_duration:.1f}s → \"{result.text[:80]}\"")
            yield result

    def has_pending_speech(self) -> bool:
        return len(self._speech_buffer) > 0

    async def flush(self) -> Optional[ASRResult]:
        """Force flush remaining speech."""
        if not self._speech_buffer:
            return None
        result = self._engine.transcribe(np.concatenate(self._speech_buffer))
        self._speech_buffer.clear()
        self._speech_duration = 0.0
        return result if result.text else None

    def reset(self) -> None:
        self._speech_buffer.clear()
        self._speech_duration = 0.0
        self._in_speech = False
        self._silence_duration = 0.0
        self._prev_text = ""
        self._total_chunks = 0

    @staticmethod
    def _bytes_to_float32(pcm_bytes: bytes) -> np.ndarray:
        return np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
