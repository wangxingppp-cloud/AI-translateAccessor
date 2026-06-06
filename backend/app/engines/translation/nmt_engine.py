"""
Neural Machine Translation engine using MarianMT.

Uses Helsinki-NLP/opus-mt-en-zh (English → Chinese) by default.
MarianMT is a family of efficient NMT models from the OPUS project,
trained on multiple language pairs.

Key characteristics:
  - Latency: 50-200ms per sentence (on GPU), 200-500ms (CPU)
  - Quality: Good for medium-length sentences, acceptable for short phrases
  - Context: Stateless — each sentence translated independently
  - Offline: Fully local, no API calls needed

The engine is initialized lazily (first request) and cached in memory.
If the model is not available, a mock translator is used for development.
"""
import time
import asyncio
from dataclasses import dataclass, field
from typing import Optional

from loguru import logger

from ...config import get_settings


@dataclass
class NMTResult:
    """Result from the NMT translation engine."""
    text: str                         # Translated text
    source_text: str                  # Original source text
    latency_ms: float = 0.0           # Translation time in ms
    timestamp: float = field(default_factory=time.time)


class NMTEngine:
    """
    MarianMT-based translation engine.

    Lazy-loads the model on first use to avoid startup delay.
    Thread-safe for concurrent translation requests.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._model_name = settings.nmt_model_path
        self._source_lang = "en"
        self._target_lang = "zh"
        self._model = None
        self._tokenizer = None
        self._device = "cpu"  # Will auto-detect on first load
        self._initialized = False

    async def translate(self, text: str, source_lang: str = "en") -> NMTResult:
        """Translate a single text segment.

        Args:
            text: Source text to translate.
            source_lang: Source language code (default: "en").

        Returns:
            NMTResult with translated text and latency metrics.
        """
        start = time.perf_counter()

        if not text.strip():
            return NMTResult(text="", source_text=text, latency_ms=0.0)

        # Lazy initialization
        if not self._initialized:
            await self._initialize()

        translated = text  # Default: echo back if no model

        if self._model is not None:
            try:
                # Run translation in a thread to avoid blocking the event loop
                translated = await asyncio.to_thread(self._translate_sync, text, source_lang)
            except Exception as e:
                logger.warning(f"NMT translation failed: {e}")
                translated = text  # Fallback to source text on error

        latency = (time.perf_counter() - start) * 1000

        return NMTResult(
            text=translated.strip(),
            source_text=text,
            latency_ms=round(latency, 1),
        )

    async def _initialize(self) -> None:
        """Lazy-load the MarianMT model and tokenizer."""
        try:
            from transformers import MarianMTModel, MarianTokenizer
            import torch

            logger.info(f"Loading NMT model: {self._model_name}...")

            self._tokenizer = await asyncio.to_thread(
                MarianTokenizer.from_pretrained, self._model_name
            )
            self._model = await asyncio.to_thread(
                MarianMTModel.from_pretrained, self._model_name
            )

            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            self._model = self._model.to(self._device)
            self._model.eval()

            logger.info(f"NMT model loaded on {self._device}")

        except ImportError:
            logger.warning(
                "transformers/torch not installed. "
                "Install with: pip install transformers torch sentencepiece"
            )
        except Exception as e:
            logger.warning(f"Failed to load NMT model: {e}")
        finally:
            self._initialized = True

    def _translate_sync(self, text: str, source_lang: str = "en") -> str:
        """Synchronous translation (runs in thread pool)."""
        if self._model is None or self._tokenizer is None:
            return text

        # MarianMT expects language-prefixed input for multilingual models,
        # or plain text for language-specific models like opus-mt-en-zh
        inputs = self._tokenizer(
            text,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=512,
        )

        inputs = {k: v.to(self._device) for k, v in inputs.items()}

        with _no_grad():
            outputs = self._model.generate(
                **inputs,
                max_length=512,
                num_beams=4,
                early_stopping=True,
                no_repeat_ngram_size=3,
            )

        return self._tokenizer.decode(outputs[0], skip_special_tokens=True)

    def is_ready(self) -> bool:
        """Check if the NMT engine is ready for translation."""
        return self._model is not None and self._initialized

    def preload(self) -> None:
        """Trigger model loading synchronously (for startup preload)."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self._initialize())
            else:
                asyncio.run(self._initialize())
        except RuntimeError:
            pass


def _no_grad():
    """Context manager for torch.no_grad(), with graceful fallback."""
    try:
        import torch
        return torch.no_grad()
    except ImportError:
        # Return a no-op context manager
        from contextlib import nullcontext
        return nullcontext()


# Singleton
_engine: Optional[NMTEngine] = None


def get_nmt_engine() -> NMTEngine:
    """Return the shared NMT engine singleton."""
    global _engine
    if _engine is None:
        _engine = NMTEngine()
    return _engine
