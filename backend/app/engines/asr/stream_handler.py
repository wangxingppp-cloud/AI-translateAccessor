"""
ASR Stream Handler — coordinates audio buffering, VAD, and ASR decode.

Two modes depending on model type:
  - streaming (Paraformer/Zipformer): Continuous feed, incremental decode.
  - offline (SenseVoice/Whisper): Accumulate speech, decode on silence.

Pipeline:
  PCM bytes → float32 → VAD filter → [stream|accumulate] → decode → ASRResult
"""
import time
import asyncio
from typing import AsyncGenerator, Optional

import numpy as np
from loguru import logger

from .sherpa_engine import SherpaASREngine, ASRResult, get_asr_engine
from .vad_processor import VadProcessor, get_vad_processor


class StreamHandler:
    """
    Per-session ASR stream handler.

    Streaming mode (Paraformer/Zipformer):
      Feed audio continuously, decode every N chunks.

    Offline mode (SenseVoice/Whisper):
      Accumulate speech segments, decode when VAD detects silence.
    """

    def __init__(self) -> None:
        self._engine = get_asr_engine()
        self._vad = get_vad_processor()
        self._stream: Optional[object] = None

        # Speech accumulation (both modes)
        self._speech_buffer: list[np.ndarray] = []
        self._speech_duration: float = 0.0
        self._total_processed: int = 0
        self._chunk_count: int = 0

        if self._engine.is_ready() and self._engine.mode == "streaming":
            self._stream = self._engine.create_stream()

    async def process_chunk(
        self, pcm_bytes: bytes
    ) -> AsyncGenerator[ASRResult, None]:
        """Process an incoming PCM audio chunk."""
        start_time = time.perf_counter()

        if len(pcm_bytes) == 0:
            return

        try:
            samples = self._bytes_to_float32(pcm_bytes)
        except Exception as e:
            logger.warning(f"PCM conversion failed: {e}")
            return

        self._total_processed += 1
        self._chunk_count += 1
        has_speech = self._vad.process(samples)

        if not has_speech:
            # Silence — if we had accumulated speech, flush it
            if self._engine.mode == "offline" and self._speech_buffer:
                result = self._engine.transcribe(
                    np.concatenate(self._speech_buffer)
                )
                self._speech_buffer.clear()
                self._speech_duration = 0.0
                if result.text:
                    yield result
            return

        # Speech detected
        self._speech_buffer.append(samples)
        self._speech_duration += len(samples) / 16000.0

        if self._engine.mode == "streaming":
            # Streaming: feed and decode periodically
            if self._stream is not None:
                self._engine.accept_waveform(self._stream, samples)

            if self._chunk_count % 3 == 0 and self._stream is not None:
                result = self._engine.decode(self._stream)
                if result.text:
                    yield result
                if result.is_final:
                    self._speech_buffer.clear()
                    self._speech_duration = 0.0

        elif self._engine.mode == "offline":
            # Offline: yield when buffer exceeds threshold
            if self._speech_duration >= 2.0:
                result = self._engine.transcribe(
                    np.concatenate(self._speech_buffer)
                )
                self._speech_buffer.clear()
                self._speech_duration = 0.0
                if result.text:
                    yield result

        elif self._engine.mode == "none":
            # No model — echo
            if self._total_processed % 10 == 0:
                yield ASRResult(
                    text=f"[{self._total_processed} chunks received — no ASR model loaded]",
                    is_final=False,
                )

    def has_pending_speech(self) -> bool:
        return len(self._speech_buffer) > 0

    async def flush(self) -> Optional[ASRResult]:
        """Flush remaining buffered speech."""
        if not self._speech_buffer:
            return None
        samples = np.concatenate(self._speech_buffer)
        self._speech_buffer.clear()
        self._speech_duration = 0.0

        if self._engine.mode == "offline":
            return self._engine.transcribe(samples)
        return None

    def reset(self) -> None:
        self._speech_buffer.clear()
        self._speech_duration = 0.0
        self._total_processed = 0
        self._chunk_count = 0
        if self._engine.mode == "streaming" and self._engine.is_ready():
            self._stream = self._engine.create_stream()

    @staticmethod
    def _bytes_to_float32(pcm_bytes: bytes) -> np.ndarray:
        return np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
