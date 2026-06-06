"""
ASR Stream Handler — VAD filtering + offline batch transcription.

SenseVoice offline mode: accumulates speech, transcribes every 1.5s.
Simple, reliable, never crashes.
"""
import asyncio
from typing import AsyncGenerator, Optional

import numpy as np
from loguru import logger

from .sherpa_engine import SherpaASREngine, ASRResult, get_asr_engine
from .vad_processor import VadProcessor, get_vad_processor

TARGET_RATE = 16000
BATCH_INTERVAL = 1.5  # seconds between transcriptions


class StreamHandler:
    """Per-session handler: VAD filter → accumulate speech → batch transcribe."""

    def __init__(self) -> None:
        self._engine = get_asr_engine()
        self._vad = get_vad_processor()
        self._speech_buffer: list[np.ndarray] = []
        self._speech_duration: float = 0.0
        self._total_processed: int = 0
        self._prev_text: str = ""

    async def process_chunk(self, pcm_bytes: bytes) -> AsyncGenerator[ASRResult, None]:
        if len(pcm_bytes) == 0:
            return

        try:
            samples = self._bytes_to_float32(pcm_bytes)
        except Exception:
            return

        self._total_processed += 1
        has_speech = self._vad.process(samples)

        if not has_speech:
            if self._speech_buffer and self._speech_duration >= 0.5:
                result = self._engine.transcribe(np.concatenate(self._speech_buffer))
                if result.text and result.text != self._prev_text:
                    self._prev_text = result.text
                    logger.debug(f"ASR: \"{result.text[:60]}\"")
                    yield result
            self._speech_buffer.clear()
            self._speech_duration = 0.0
            return

        self._speech_buffer.append(samples)
        self._speech_duration += len(samples) / TARGET_RATE

        # Batch transcribe at interval
        if self._speech_duration >= BATCH_INTERVAL:
            result = self._engine.transcribe(np.concatenate(self._speech_buffer))
            if result.text and result.text != self._prev_text:
                self._prev_text = result.text
                logger.info(f"ASR: \"{result.text[:80]}\"")
                yield result
            self._speech_buffer.clear()
            self._speech_duration = 0.0

    def has_pending_speech(self) -> bool:
        return len(self._speech_buffer) > 0

    async def flush(self) -> Optional[ASRResult]:
        if not self._speech_buffer:
            return None
        result = self._engine.transcribe(np.concatenate(self._speech_buffer))
        self._speech_buffer.clear()
        self._speech_duration = 0.0
        return result if result.text else None

    def reset(self) -> None:
        self._speech_buffer.clear()
        self._speech_duration = 0.0
        self._total_processed = 0
        self._prev_text = ""

    @staticmethod
    def _bytes_to_float32(pcm_bytes: bytes) -> np.ndarray:
        return np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
