"""
Sherpa-onnx ASR Engine — streaming (Paraformer/Zipformer) + offline (SenseVoice).

Auto-detects model type from available files:
  - encoder/decoder ONNX → OnlineRecognizer (streaming Paraformer/Zipformer)
  - model.onnx + tokens → OfflineRecognizer (SenseVoice, Whisper)

SenseVoice: zh, en, ja, ko, yue — ~200MB
  Download: python scripts/download_model.py
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
    text: str
    is_final: bool = False
    confidence: float = 0.0
    timestamp: float = field(default_factory=time.time)
    tokens: list[str] = field(default_factory=list)


class SherpaASREngine:
    """
    Streaming + offline ASR engine backed by sherpa-onnx.

    One instance is shared across all WebSocket sessions.
    Each session creates its own stream and feeds audio independently.
    """

    def __init__(self) -> None:
        settings = get_settings()

        model_dir = settings.resolved_models_dir / "sherpa-onnx-paraformer"
        if settings.asr_model_path:
            model_dir = Path(settings.asr_model_path)

        if not model_dir.exists():
            logger.warning(f"ASR model not found at {model_dir}")
            self._recognizer = None
            self._sample_rate = 16000
            self._mode = "none"
            return

        self._sample_rate = settings.asr_sample_rate
        self._mode = "none"
        self._recognizer = None  # OnlineRecognizer | OfflineRecognizer

        # Try streaming first (Paraformer/Zipformer)
        encoder = self._find_file(model_dir, "encoder", ".onnx")
        decoder = self._find_file(model_dir, "decoder", ".onnx")
        tokens = self._find_file(model_dir, "tokens", ".txt")

        if encoder and decoder and tokens:
            self._recognizer = sherpa_onnx.OnlineRecognizer(
                nn_model=encoder,
                paraformer=decoder,
                tokens=tokens,
                sample_rate=self._sample_rate,
                feature_dim=settings.asr_feature_dim,
                decoding_method="greedy_search",
                num_active_paths=4,
            )
            self._mode = "streaming"
            logger.info(f"ASR: streaming mode ({model_dir.name})")
            return

        # Try offline (SenseVoice, Whisper) — prefer INT8 quantized model
        model = self._find_file(model_dir, "model.int8", ".onnx") or \
                self._find_file(model_dir, "model", ".onnx")
        if model and tokens:
            self._recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
                model=model,
                tokens=tokens,
            )
            self._mode = "offline"
            logger.info(f"ASR: offline mode ({model_dir.name})")
            return

        logger.error(f"ASR model files incomplete in {model_dir}")
        self._recognizer = None
        self._mode = "none"

    # ── Streaming API (Paraformer/Zipformer) ────────────────────

    def create_stream(self) -> Optional[sherpa_onnx.OnlineStream]:
        if self._mode != "streaming" or self._recognizer is None:
            return None
        return self._recognizer.create_stream()

    def accept_waveform(
        self, stream: sherpa_onnx.OnlineStream, samples: np.ndarray
    ) -> None:
        if self._mode != "streaming" or self._recognizer is None:
            return
        stream.accept_waveform(self._sample_rate, samples.astype(np.float32))

    def decode(self, stream: sherpa_onnx.OnlineStream) -> ASRResult:
        if self._mode != "streaming" or self._recognizer is None:
            return ASRResult(text="", is_final=False)

        self._recognizer.decode_stream(stream)
        text = stream.result.text.strip()
        is_endpoint = stream.is_endpoint

        if is_endpoint:
            self._recognizer.reset(stream)

        return ASRResult(text=text, is_final=is_endpoint, timestamp=time.time())

    # ── Offline API (SenseVoice, Whisper) ───────────────────────

    def transcribe(self, samples: np.ndarray) -> ASRResult:
        """Transcribe accumulated speech audio (used with VAD)."""
        if self._mode != "offline" or self._recognizer is None:
            return ASRResult(text="", is_final=True)

        if len(samples) < self._sample_rate * 0.3:  # Skip <300ms
            return ASRResult(text="", is_final=True)

        stream = self._recognizer.create_stream()
        stream.accept_waveform(self._sample_rate, samples.astype(np.float32))
        self._recognizer.decode_stream(stream)
        text = stream.result.text.strip()

        return ASRResult(text=text, is_final=True, timestamp=time.time())

    # ── Common ─────────────────────────────────────────────────

    def is_ready(self) -> bool:
        return self._recognizer is not None and self._mode != "none"

    @property
    def mode(self) -> str:
        return self._mode

    @staticmethod
    def _find_file(model_dir: Path, stem: str, suffix: str) -> Optional[str]:
        candidates = list(model_dir.glob(f"*{stem}*{suffix}"))
        if not candidates:
            candidates = [c for c in model_dir.glob(f"*{suffix}") if stem.lower() in c.name.lower()]
        return str(candidates[0]) if candidates else None


_engine: Optional[SherpaASREngine] = None


def get_asr_engine() -> SherpaASREngine:
    global _engine
    if _engine is None:
        _engine = SherpaASREngine()
    return _engine
