"""
ASR Stream Handler — coordinates audio buffering, VAD, and ASR decode.

Handles variable input formats by resampling to 16kHz mono float32.
"""
import time
import asyncio
from typing import AsyncGenerator, Optional

import numpy as np
from loguru import logger

from .sherpa_engine import SherpaASREngine, ASRResult, get_asr_engine
from .vad_processor import VadProcessor, get_vad_processor

TARGET_RATE = 16000


class StreamHandler:
    """Per-session ASR stream handler with adaptive input resampling."""

    def __init__(self, input_rate: int = 0, input_channels: int = 0, input_bits: int = 0) -> None:
        self._engine = get_asr_engine()
        self._vad = get_vad_processor()
        self._stream: Optional[object] = None

        self._speech_buffer: list[np.ndarray] = []
        self._speech_duration: float = 0.0
        self._total_processed: int = 0
        self._chunk_count: int = 0

        # Input format (0 = assume already 16kHz mono)
        self._input_rate = input_rate or TARGET_RATE
        self._input_channels = input_channels or 1
        self._input_bits = input_bits or 16

        if input_rate and input_rate != TARGET_RATE:
            logger.info(f"StreamHandler: resample {input_rate}Hz {input_channels}ch {input_bits}bit → 16kHz mono")

        if self._engine.is_ready() and self._engine.mode == "streaming":
            self._stream = self._engine.create_stream()

    async def process_chunk(self, pcm_bytes: bytes) -> AsyncGenerator[ASRResult, None]:
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
        self._total_processed += 1
        self._chunk_count += 1

        if not has_speech:
            if self._engine.mode == "offline" and self._speech_buffer:
                dur = self._speech_duration
                if dur >= 0.5:
                    result = self._engine.transcribe(np.concatenate(self._speech_buffer))
                    if result.text:
                        yield result
                self._speech_buffer.clear()
                self._speech_duration = 0.0
            return

        self._speech_buffer.append(samples)
        self._speech_duration += len(samples) / TARGET_RATE

        # Force flush every 3s even without silence (offline mode)
        if self._engine.mode == "offline" and self._speech_duration >= 3.0:
            result = self._engine.transcribe(np.concatenate(self._speech_buffer))
            if result.text:
                yield result
            self._speech_buffer.clear()
            self._speech_duration = 0.0

        if self._engine.mode == "streaming":
            if self._stream is not None:
                self._engine.accept_waveform(self._stream, samples)
                result = self._engine.decode(self._stream)
                if result.text:
                    yield result
                if result.is_final:
                    self._speech_buffer.clear()
                    self._speech_duration = 0.0

    def has_pending_speech(self) -> bool:
        return len(self._speech_buffer) > 0

    async def flush(self) -> Optional[ASRResult]:
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

    # ── Format conversion ──────────────────────────────────────

    def _bytes_to_float32(self, pcm_bytes: bytes) -> np.ndarray:
        """Convert raw PCM bytes to float32 mono at TARGET_RATE Hz."""
        src_rate = self._input_rate
        src_ch = self._input_channels
        src_bits = self._input_bits

        # Step 1: Bytes → samples based on bit depth
        if src_bits == 32:
            # 32-bit IEEE float
            samples = np.frombuffer(pcm_bytes, dtype=np.float32)
        elif src_bits == 16:
            samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        elif src_bits == 24:
            # 24-bit → pad to 32-bit
            raw = np.frombuffer(pcm_bytes, dtype=np.uint8)
            raw = raw.reshape(-1, 3)
            padded = np.pad(raw, ((0, 0), (0, 1)), 'constant')
            samples = padded.view(np.int32).flatten().astype(np.float32) / 8388608.0
        else:
            samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        # Step 2: Stereo → Mono (average channels)
        if src_ch == 2:
            samples = samples.reshape(-1, 2).mean(axis=1)
        elif src_ch > 2:
            samples = samples.reshape(-1, src_ch)[:, :2].mean(axis=1)

        # Step 3: Resample to 16kHz (simple linear interpolation)
        if src_rate != TARGET_RATE and len(samples) > 1:
            n_out = int(len(samples) * TARGET_RATE / src_rate)
            idx = np.linspace(0, len(samples) - 1, n_out)
            lo = np.floor(idx).astype(int)
            hi = np.clip(lo + 1, 0, len(samples) - 1)
            frac = idx - lo
            samples = samples[lo] * (1 - frac) + samples[hi] * frac

        return samples.astype(np.float32)
