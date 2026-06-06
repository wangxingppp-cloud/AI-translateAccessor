"""
Neural Machine Translation engine.

Architecture for desktop packaging (NO PyTorch dependency):
  Primary:  ONNX Runtime + ONNX-converted OPUS-MT model (~250MB)
            Uses the same ONNX Runtime that sherpa-onnx already depends on.
            Zero additional runtime dependencies.

  Fallback: transformers + MarianMT (for development, optional)
            Only used if ONNX model not found and transformers is installed.

  Echo:     Returns source text unchanged (dev mode without any model).

All three backends share the same `translate()` interface.
The backend auto-selects based on available dependencies and model files.
"""
import time
import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
from loguru import logger

from ...config import get_settings


@dataclass
class NMTResult:
    """Result from the NMT translation engine."""
    text: str                         # Translated text
    source_text: str                  # Original source text
    latency_ms: float = 0.0
    backend: str = ""                 # Which backend was used
    timestamp: float = field(default_factory=time.time)


class NMTEngine:
    """
    Multi-backend NMT engine for English → Chinese translation.

    Backend priority (auto-selected):
      1. ONNX Runtime (production, no PyTorch needed, desktop-packable)
      2. Transformers  (development, needs PyTorch)
      3. Echo           (fallback, returns source text)

    Model preparation for ONNX:
      Download OPUS-MT en→zh ONNX model from HuggingFace or convert manually.
      Place files in:  {models_dir}/opus-mt-en-zh/
        - model.onnx
        - tokenizer.json  (or vocab files)
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._model_dir = settings.resolved_models_dir / "opus-mt-en-zh"
        self._backend = self._detect_backend()
        self._initialized = False

        # Backend-specific state
        self._session = None          # onnxruntime.InferenceSession
        self._tokenizer = None        # Tokenizer instance
        self._model = None            # transformers model (fallback)
        self._device = "cpu"

    async def translate(self, text: str, source_lang: str = "en",
                        glossary_terms: list[dict] | None = None) -> NMTResult:
        """Translate a single text segment.

        Args:
            text: Source text (English).
            source_lang: Source language code (default: "en").
            glossary_terms: Optional list of {source, target} term pairs.

        Returns:
            NMTResult with translated text and metadata.
        """
        start = time.perf_counter()

        if not text.strip():
            return NMTResult(text="", source_text=text, backend=self._backend)

        if not self._initialized:
            await self._initialize()

        translated = text  # Default: echo back

        try:
            if self._backend == "onnx":
                translated = await asyncio.to_thread(self._translate_onnx, text)
            elif self._backend == "transformers":
                translated = await asyncio.to_thread(self._translate_transformers, text)
            # "echo" backend: just return text as-is
        except Exception as e:
            logger.warning(f"NMT [{self._backend}] translation failed: {e}")

        latency = (time.perf_counter() - start) * 1000

        return NMTResult(
            text=translated.strip(),
            source_text=text,
            latency_ms=round(latency, 1),
            backend=self._backend,
        )

    # ── Backend detection ───────────────────────────────────────

    def _detect_backend(self) -> str:
        """Auto-select the best available backend."""
        # ONNX: check for encoder/decoder ONNX files (any filename pattern)
        enc_files = list(self._model_dir.glob("encoder_model*.onnx"))
        dec_files = list(self._model_dir.glob("decoder_model*.onnx"))
        if enc_files and dec_files:
            logger.info(f"NMT: ONNX model found at {self._model_dir}")
            return "onnx"

        # Transformers: check if library is importable
        try:
            import transformers  # noqa: F401
            logger.info("NMT: Using transformers backend (pip install transformers torch)")
            return "transformers"
        except ImportError:
            pass

        # Echo fallback
        logger.warning(
            "NMT: No model available — echoing source text.\n"
            "For production: place ONNX model at models/opus-mt-en-zh/model.onnx\n"
            "For development: pip install transformers torch sentencepiece"
        )
        return "echo"

    async def _initialize(self) -> None:
        """Lazy-initialize the selected backend."""
        try:
            if self._backend == "onnx":
                await self._init_onnx()
            elif self._backend == "transformers":
                await self._init_transformers()
        finally:
            self._initialized = True

    # ── ONNX backend ────────────────────────────────────────────

    async def _init_onnx(self) -> None:
        """Initialize ONNX Runtime with encoder + decoder + vocab."""
        import onnxruntime as ort
        import sentencepiece as spm
        import json

        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        opts.intra_op_num_threads = 4
        providers = ort.get_available_providers()

        enc_path = str(next(self._model_dir.glob("encoder_model*.onnx")))
        dec_path = str(next(self._model_dir.glob("decoder_model*.onnx")))

        self._enc_sess = await asyncio.to_thread(
            ort.InferenceSession, enc_path, opts, providers=providers)
        self._dec_sess = await asyncio.to_thread(
            ort.InferenceSession, dec_path, opts, providers=providers)

        # Source tokenizer (SentencePiece, works for English)
        self._src_spm = spm.SentencePieceProcessor()
        self._src_spm.Load(str(self._model_dir / "source.spm"))

        # Target vocab (65001 tokens, use vocab.json for decoding)
        with open(self._model_dir / "vocab.json", encoding="utf-8") as f:
            vocab = json.load(f)
        self._id2token = {int(v): k for k, v in vocab.items()}

        logger.info(f"NMT ONNX backend ready ({providers})")

    def _translate_onnx(self, text: str) -> str:
        """Translate using ONNX encoder-decoder."""
        # Tokenize with source SentencePiece
        input_ids = self._src_spm.encode(text, out_type=int)
        if not input_ids:
            return text

        input_ids = np.array([input_ids], dtype=np.int64)
        attention_mask = np.ones(input_ids.shape, dtype=np.int64)

        # Encode
        enc_out = self._enc_sess.run(
            None, {"input_ids": input_ids, "attention_mask": attention_mask}
        )[0]

        # Autoregressive decode
        start_id = 65000  # <pad> = decoder_start_token_id
        eos_id = 0        # </s> = eos_token_id
        decoder_input = np.array([[start_id]], dtype=np.int64)
        max_len = 128
        output_ids = []

        for _ in range(max_len):
            dec_out = self._dec_sess.run(
                None, {
                    "input_ids": decoder_input,
                    "encoder_hidden_states": enc_out,
                    "encoder_attention_mask": attention_mask,
                }
            )
            logits = dec_out[0][0, -1, :]
            next_id = int(np.argmax(logits))
            if next_id == eos_id:
                break
            output_ids.append(next_id)
            decoder_input = np.hstack([decoder_input, np.array([[next_id]], dtype=np.int64)])

        # Decode with full 65001 vocab
        if output_ids:
            raw = "".join(self._id2token.get(tid, "") for tid in output_ids)
            # SentencePiece detokenization: remove ▁ markers
            text = raw.replace("▁", " ").strip()
            return text
        return text

    # ── Transformers backend (dev only) ─────────────────────────

    async def _init_transformers(self) -> None:
        """Initialize HuggingFace MarianMT for development."""
        from transformers import MarianMTModel, MarianTokenizer
        import torch

        model_name = "Helsinki-NLP/opus-mt-en-zh"

        self._tokenizer = await asyncio.to_thread(MarianTokenizer.from_pretrained, model_name)
        self._model = await asyncio.to_thread(MarianMTModel.from_pretrained, model_name)
        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model = self._model.to(self._device).eval()

        logger.info(f"NMT transformers backend ready on {self._device}")

    def _translate_transformers(self, text: str) -> str:
        """Translate using HuggingFace MarianMT."""
        if self._model is None or self._tokenizer is None:
            return text

        # Import here to avoid top-level torch dependency
        import torch

        inputs = self._tokenizer(text, return_tensors="pt", padding=True, truncation=True)
        inputs = {k: v.to(self._device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self._model.generate(**inputs, max_length=512, num_beams=4)

        return self._tokenizer.decode(outputs[0], skip_special_tokens=True)

    # ── Public API ──────────────────────────────────────────────

    def is_ready(self) -> bool:
        """Check if a real translation backend is active."""
        return self._backend in ("onnx", "transformers")

    @property
    def backend_name(self) -> str:
        return self._backend


# Singleton
_engine: Optional[NMTEngine] = None


def get_nmt_engine() -> NMTEngine:
    global _engine
    if _engine is None:
        _engine = NMTEngine()
    return _engine
