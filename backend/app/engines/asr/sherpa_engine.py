"""
Sherpa-onnx Streaming ASR Engine.

Wraps sherpa_onnx.OnlineRecognizer for real-time speech recognition.
Supports Paraformer (Chinese-optimized) and other transducer/CTC models.

Model preparation:
  Pre-converted models are available at:
  https://github.com/k2-fsa/sherpa-onnx/releases

  For Chinese (Paraformer):
    sherpa-onnx-paraformer-zh-small-2024-03-09.tar.bz2

  For English:
    sherpa-onnx-zipformer-en-2023-06-26.tar.bz2

  Usage:
    ASR_MODEL_PATH=/path/to/extracted/model

The engine handles:
  - Streaming waveform acceptance (accept_waveform)
  - Incremental decoding (decode_stream)
  - Endpoint detection (is_endpoint)
  - Result retrieval and stream reset
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
class ASRResult:
    """Single ASR recognition result."""
    text: str                         # Recognized text (partial or final)
    is_final: bool = False            # True if utterance has ended
    confidence: float = 0.0           # Confidence score (0-1)
    timestamp: float = field(default_factory=time.time)
    tokens: list[str] = field(default_factory=list)


class SherpaASREngine:
    """
    Streaming ASR engine backed by sherpa-onnx.

    One instance is shared across all WebSocket sessions.
    Each session creates its own OnlineStream and feeds audio independently.
    """

    def __init__(self) -> None:
        settings = get_settings()

        model_dir = settings.resolved_models_dir / "sherpa-onnx-paraformer"
        if settings.asr_model_path:
            model_dir = Path(settings.asr_model_path)

        if not model_dir.exists():
            logger.warning(
                f"ASR model not found at {model_dir}. "
                f"Download from https://github.com/k2-fsa/sherpa-onnx/releases"
            )
            # Create a placeholder recognizer that returns empty results
            self._recognizer = None
            self._sample_rate = 16000
            return

        # Determine the model type from available files
        encoder = self._find_file(model_dir, "encoder", ".onnx")
        decoder = self._find_file(model_dir, "decoder", ".onnx")
        tokens = self._find_file(model_dir, "tokens", ".txt")

        if not encoder or not decoder or not tokens:
            logger.error(f"ASR model files incomplete in {model_dir}")
            self._recognizer = None
            self._sample_rate = 16000
            return

        # Create the online recognizer
        self._recognizer = sherpa_onnx.OnlineRecognizer(
            nn_model=encoder,
            paraformer=decoder,
            tokens=tokens,
            sample_rate=settings.asr_sample_rate,
            feature_dim=settings.asr_feature_dim,
            decoding_method="greedy_search",
            num_active_paths=4,
        )

        self._sample_rate = settings.asr_sample_rate

        logger.info(
            f"ASR engine initialized: {model_dir.name} "
            f"({self._sample_rate} Hz, feature_dim={settings.asr_feature_dim})"
        )

    def create_stream(self) -> Optional[sherpa_onnx.OnlineStream]:
        """Create a new recognition stream for a session."""
        if self._recognizer is None:
            return None
        return self._recognizer.create_stream()

    def accept_waveform(
        self,
        stream: sherpa_onnx.OnlineStream,
        samples: np.ndarray,
    ) -> None:
        """Feed audio samples to the recognition stream.

        Args:
            stream: The recognition stream created by create_stream().
            samples: float32 numpy array, shape (num_samples,).
        """
        if self._recognizer is None:
            return
        stream.accept_waveform(self._sample_rate, samples.astype(np.float32))

    def decode(self, stream: sherpa_onnx.OnlineStream) -> ASRResult:
        """Decode the current stream and return incremental result.

        Returns the partial recognition result. The text may change
        as more audio is fed — this is expected behavior for streaming ASR.
        """
        if self._recognizer is None:
            return ASRResult(text="", is_final=False)

        self._recognizer.decode_stream(stream)
        text = stream.result.text
        is_endpoint = stream.is_endpoint

        # Reset stream after endpoint detected
        if is_endpoint:
            self._recognizer.reset(stream)

        return ASRResult(
            text=text.strip(),
            is_final=is_endpoint,
            timestamp=time.time(),
        )

    def is_ready(self) -> bool:
        """Check if the engine is initialized with a valid model."""
        return self._recognizer is not None

    # ── Helpers ────────────────────────────────────────────────

    @staticmethod
    def _find_file(model_dir: Path, stem: str, suffix: str) -> Optional[str]:
        """Find a model file by name stem and suffix.

        e.g. _find_file(model_dir, "encoder", ".onnx") finds
        model_dir/encoder-xxx.onnx or model_dir/xxx-encoder.onnx.
        """
        candidates = list(model_dir.glob(f"*{stem}*{suffix}"))
        if not candidates:
            candidates = list(model_dir.glob(f"*{suffix}"))
            candidates = [c for c in candidates if stem.lower() in c.name.lower()]

        if candidates:
            return str(candidates[0])

        logger.warning(f"File not found: *{stem}*{suffix} in {model_dir}")
        return None


# Singleton shared across all sessions
_engine: Optional[SherpaASREngine] = None


def get_asr_engine() -> SherpaASREngine:
    """Return (and lazily initialize) the shared ASR engine singleton."""
    global _engine
    if _engine is None:
        _engine = SherpaASREngine()
    return _engine
