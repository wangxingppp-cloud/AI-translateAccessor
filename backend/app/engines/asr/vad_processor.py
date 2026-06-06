"""
Voice Activity Detection (VAD) processor — energy-based.

Detects speech vs silence using RMS energy threshold.
Calibrated for system audio (WASAPI loopback) at 16kHz mono float32.
"""
import numpy as np
from loguru import logger

# System audio: speech RMS 0.02-0.20, silence < 0.005
SPEECH_THRESHOLD = 0.008


class VadProcessor:
    """Energy-based VAD for sentence boundary detection."""

    def __init__(self) -> None:
        self._total = 0
        logger.info(f"VAD: energy-based, threshold={SPEECH_THRESHOLD}")

    def process(self, samples: np.ndarray) -> bool:
        """Returns True if speech detected, False if silence."""
        if len(samples) == 0:
            return False
        s = samples.astype(np.float32)
        rms = np.sqrt(np.mean(s ** 2))
        self._total += 1
        if self._total <= 5 or self._total % 50 == 0:
            logger.info(f"VAD #{self._total}: rms={rms:.4f} speech={rms>=SPEECH_THRESHOLD}")
        return rms >= SPEECH_THRESHOLD

    def reset(self) -> None:
        self._total = 0

    def is_ready(self) -> bool:
        return True


_vad = VadProcessor()


def get_vad_processor() -> VadProcessor:
    return _vad
