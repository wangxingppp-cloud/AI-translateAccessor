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
BATCH_INTERVAL = 2.5  # seconds between transcriptions


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
                audio = np.concatenate(self._speech_buffer)
                self._speech_buffer.clear()
                self._speech_duration = 0.0
                result = await asyncio.to_thread(self._engine.transcribe, audio)
                # Note: silence flush doesn't need overlap (utterance ended)
                if result.text and result.text != self._prev_text:
                    self._prev_text = result.text
                    logger.debug(f"ASR: \"{result.text[:60]}\"")
                    yield result
            self._speech_duration = 0.0
            return

        self._speech_buffer.append(samples)
        self._speech_duration += len(samples) / TARGET_RATE

        # Batch transcribe with overlap (preserves context across batches)
        if self._speech_duration >= BATCH_INTERVAL:
            audio = np.concatenate(self._speech_buffer)
            # Keep last 400ms for next batch overlap
            overlap_samples = int(TARGET_RATE * 0.4)
            if len(audio) > overlap_samples:
                overlap = audio[-overlap_samples:]
            else:
                overlap = np.array([], dtype=np.float32)
            self._speech_buffer.clear()
            self._speech_duration = 0.0
            result = await asyncio.to_thread(self._engine.transcribe, audio)
            # Prepend overlap to next batch
            if len(overlap) > 0:
                self._speech_buffer.append(overlap)
                self._speech_duration = len(overlap) / TARGET_RATE
            if result.text and result.text != self._prev_text:
                self._prev_text = result.text
                logger.info(f"ASR: \"{result.text[:80]}\"")
                yield result

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
