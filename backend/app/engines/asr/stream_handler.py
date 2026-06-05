"""
ASR Stream Handler — coordinates audio buffering, VAD, and ASR decode.

Each WebSocket session gets one StreamHandler instance.
Audio chunks are fed via process_chunk(), and ASR results are
yielded via the async generator.

Pipeline:
  PCM bytes → float32 samples → VAD filter → ASR feed → decode → result
                      ↑                    ↑
                 (skip silence)      (accumulate speech)
"""
import time
import asyncio
import struct
from typing import AsyncGenerator, Optional

import numpy as np
from loguru import logger

from .sherpa_engine import SherpaASREngine, ASRResult, get_asr_engine
from .vad_processor import VadProcessor, get_vad_processor


class StreamHandler:
    """
    Per-session ASR stream handler.

    Manages the lifecycle of one recognition stream:
      - Receives raw PCM bytes
      - Converts to float32 samples
      - Runs VAD to filter silence
      - Feeds speech to ASR
      - Yields ASR results

    Usage in WebSocket handler:
        handler = StreamHandler()
        async for result in handler.process_chunk(pcm_bytes):
            await ws.send_json(result)
    """

    def __init__(self) -> None:
        self._engine = get_asr_engine()
        self._vad = get_vad_processor()
        self._stream: Optional[object] = None  # sherpa_onnx.OnlineStream

        # Buffered speech samples (accumulated between VAD segments)
        self._speech_buffer: list[np.ndarray] = []
        self._speech_duration: float = 0.0  # seconds
        self._total_processed: int = 0       # total chunks processed

        # Performance tracking
        self._chunk_count: int = 0
        self._last_decode: float = 0.0

        # Create ASR stream if engine is ready
        if self._engine.is_ready():
            self._stream = self._engine.create_stream()

    async def process_chunk(
        self,
        pcm_bytes: bytes,
    ) -> AsyncGenerator[ASRResult, None]:
        """
        Process an incoming PCM audio chunk.

        Args:
            pcm_bytes: Raw 16-bit little-endian PCM bytes (16kHz mono).

        Yields:
            ASRResult with incremental recognition text.
        """
        start_time = time.perf_counter()

        if len(pcm_bytes) == 0:
            return

        # Convert bytes → float32 samples
        try:
            samples = self._bytes_to_float32(pcm_bytes)
        except Exception as e:
            logger.warning(f"PCM conversion failed: {e}")
            return

        self._total_processed += 1

        # VAD: skip silent chunks
        has_speech = self._vad.process(samples)

        if has_speech:
            # Feed to ASR stream
            self._speech_buffer.append(samples)
            self._speech_duration += len(samples) / 16000.0

            if self._stream is not None:
                self._engine.accept_waveform(self._stream, samples)

        # Decode every N chunks or when speech buffer reaches threshold
        self._chunk_count += 1
        decode_interval = 3  # Decode every 3 chunks (~600ms)
        speech_threshold = 1.0  # Or when 1 second of speech accumulated

        should_decode = (
            (self._chunk_count % decode_interval == 0) or
            (self._speech_duration >= speech_threshold and has_speech)
        )

        if should_decode and self._stream is not None:
            result = self._engine.decode(self._stream)

            if result.text:
                decode_time = (time.perf_counter() - start_time) * 1000
                logger.debug(
                    f"ASR [{self._total_processed} chunks, "
                    f"{self._speech_duration:.1f}s speech]: "
                    f"\"{result.text}\" (decode: {decode_time:.0f}ms)"
                )
                yield result

            # If endpoint detected, flush speech buffer
            if result.is_final and self._speech_buffer:
                logger.info(
                    f"Utterance end after {self._speech_duration:.1f}s, "
                    f"{len(self._speech_buffer)} chunks"
                )
                self._speech_buffer.clear()
                self._speech_duration = 0.0

    def has_pending_speech(self) -> bool:
        """Check if there is un-decoded speech in the buffer."""
        return len(self._speech_buffer) > 0

    async def flush(self) -> Optional[ASRResult]:
        """Force a final decode of buffered speech and return the result."""
        if not self._speech_buffer or self._stream is None:
            return None

        # Feed any remaining buffered chunks
        for chunk in self._speech_buffer:
            self._engine.accept_waveform(self._stream, chunk)

        result = self._engine.decode(self._stream)
        self._speech_buffer.clear()
        self._speech_duration = 0.0

        return result if result.text else None

    def reset(self) -> None:
        """Reset the stream for a new session."""
        self._speech_buffer.clear()
        self._speech_duration = 0.0
        self._total_processed = 0
        if self._engine.is_ready():
            self._stream = self._engine.create_stream()

    @staticmethod
    def _bytes_to_float32(pcm_bytes: bytes) -> np.ndarray:
        """Convert raw 16-bit PCM bytes to float32 numpy array."""
        # Interpret bytes as int16 little-endian
        int16_samples = np.frombuffer(pcm_bytes, dtype=np.int16)
        # Normalize to [-1.0, +1.0]
        return int16_samples.astype(np.float32) / 32768.0
