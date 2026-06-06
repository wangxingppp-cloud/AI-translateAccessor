"""
Voice Activity Detection (VAD) processor.

Wraps sherpa-onnx's built-in Silero VAD model for detecting
speech vs silence in audio chunks.

Used by the ASR pipeline to:
  - Skip silent audio chunks (saves CPU/GPU)
  - Detect utterance boundaries (end-of-speech)

The VAD runs on each incoming audio chunk before ASR processing.
"""
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import sherpa_onnx
from loguru import logger

from ...config import get_settings


@dataclass
class VADResult:
    """Per-chunk VAD classification result."""
    has_speech: bool
    timestamp: float = field(default_factory=time.time)


class VadProcessor:
    """
    Voice Activity Detector using Silero VAD via sherpa-onnx.

    Stateful — accumulates consecutive silence/speech durations
    to determine utterance boundaries.
    """

    def __init__(self) -> None:
        settings = get_settings()

        model_dir = settings.resolved_models_dir / "silero-vad"
        silero_vad_path = str(model_dir / "silero_vad.onnx")

        if not Path(silero_vad_path).exists():
            logger.warning(
                f"VAD model not found at {silero_vad_path}. "
                f"VAD will be disabled — all audio treated as speech."
            )
            self._vad = None
            self._sample_rate = settings.asr_sample_rate
            self._threshold = settings.vad_threshold
            self._min_speech = settings.min_speech_duration
            self._min_silence = settings.min_silence_duration
            return

        config = sherpa_onnx.VadModelConfig()
        config.silero_vad.model = silero_vad_path
        config.silero_vad.threshold = settings.vad_threshold
        config.silero_vad.min_silence_duration = settings.min_silence_duration
        config.silero_vad.min_speech_duration = settings.min_speech_duration
        config.sample_rate = settings.asr_sample_rate

        self._vad = sherpa_onnx.VoiceActivityDetector(config)
        self._sample_rate = settings.asr_sample_rate
        self._threshold = settings.vad_threshold
        self._min_speech = settings.min_speech_duration
        self._min_silence = settings.min_silence_duration

        logger.info(
            f"VAD initialized: threshold={self._threshold}, "
            f"min_speech={self._min_speech}s, min_silence={self._min_silence}s"
        )

    def process(self, samples: np.ndarray) -> bool:
        """Classify a chunk of audio as speech or silence.

        Uses two-stage detection:
          1. Energy check (fast, per-chunk) — rejects obvious silence
          2. VAD feed (accumulates context for segment boundaries)

        Returns:
            True if the chunk likely contains speech, False if silence.
        """
        if len(samples) == 0:
            return False

        s = samples.astype(np.float32)

        # Stage 1: Energy-based fast filter
        rms = np.sqrt(np.mean(s ** 2))
        self._n = getattr(self, '_n', 0) + 1
        if self._n <= 5 or self._n % 30 == 0:
            logger.info(f"VAD #{self._n}: rms={rms:.4f} speech={rms>=0.0005}")
        if rms < 0.0005:  # Block only pure silence
            return False

        # Stage 2: Feed to VAD model for context accumulation
        if self._vad is not None:
            self._vad.accept_waveform(s)

        # Energy above threshold → likely speech
        return True

    def detect_endpoint(self, samples: np.ndarray) -> bool:
        """Check if this chunk marks the end of an utterance.

        Returns True when enough silence has passed after speech
        to constitute an utterance boundary.
        """
        if self._vad is None:
            return False

        samples = samples.astype(np.float32)
        self._vad.accept_waveform(samples)

        # The VAD internally tracks speech/silence segments.
        # After feeding audio, check if the latest segment is silence
        # and if the preceding segment was speech.
        has_speech_seen = False
        last_is_silence = False

        while not self._vad.empty():
            segment = self._vad.front()
            self._vad.pop()
            if len(segment.samples) > 0:
                has_speech_seen = True
            else:
                last_is_silence = True

        return has_speech_seen and last_is_silence

    def reset(self) -> None:
        """Reset internal VAD state (e.g. between utterances)."""
        if self._vad is not None:
            self._vad.reset()

    def is_ready(self) -> bool:
        return self._vad is not None


# Singleton
_vad: Optional[VadProcessor] = None


def get_vad_processor() -> VadProcessor:
    global _vad
    if _vad is None:
        _vad = VadProcessor()
    return _vad
