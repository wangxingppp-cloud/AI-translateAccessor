"""
Local NMT engine using ONNX Runtime (Helsinki-NLP/opus-mt-en-zh).

Fast (~100-300ms) local translation without API calls.
"""
import time
import numpy as np
import onnxruntime as ort
from loguru import logger

try:
    from transformers import AutoTokenizer
    _HAS_TRANSFORMERS = True
except ImportError:
    _HAS_TRANSFORMERS = False


class NMTEngine:
    """Local NMT translation using ONNX quantized model."""

    def __init__(self, model_dir: str = "models/nmt-en-zh"):
        self._ready = False
        self._encoder = None
        self._decoder = None
        self._tokenizer = None

        if not _HAS_TRANSFORMERS:
            logger.warning("transformers not installed, NMT disabled")
            return

        try:
            t0 = time.time()
            self._encoder = ort.InferenceSession(
                f"{model_dir}/onnx/encoder_model.onnx",
                providers=["CPUExecutionProvider"],
            )
            self._decoder = ort.InferenceSession(
                f"{model_dir}/onnx/decoder_model.onnx",
                providers=["CPUExecutionProvider"],
            )
            self._tokenizer = AutoTokenizer.from_pretrained(model_dir)
            self._ready = True
            logger.info(f"NMT engine loaded in {time.time()-t0:.2f}s ({model_dir})")
        except Exception as e:
            logger.warning(f"NMT engine load failed: {e}")

    @property
    def ready(self) -> bool:
        return self._ready

    def translate(self, text: str) -> str:
        """Translate English text to Chinese. Returns empty string if failed."""
        if not self._ready or not text.strip():
            return ""

        try:
            inputs = self._tokenizer(text, return_tensors="np")
            input_ids = inputs["input_ids"].astype(np.int64)
            attention_mask = inputs["attention_mask"].astype(np.int64)

            enc_out = self._encoder.run(None, {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
            })

            decoder_ids = np.array([[self._tokenizer.pad_token_id or 0]], dtype=np.int64)
            for _ in range(128):
                dec_out = self._decoder.run(None, {
                    "input_ids": decoder_ids,
                    "encoder_hidden_states": enc_out[0],
                    "encoder_attention_mask": attention_mask,
                })
                next_token = np.argmax(dec_out[0][:, -1, :], axis=-1)
                decoder_ids = np.concatenate([decoder_ids, next_token.reshape(1, 1)], axis=1)
                if next_token[0] == self._tokenizer.eos_token_id:
                    break

            result = self._tokenizer.decode(decoder_ids[0], skip_special_tokens=True)
            return result.strip()
        except Exception as e:
            logger.warning(f"NMT translate error: {e}")
            return ""


# Singleton instance
_nmt_engine: NMTEngine | None = None


def get_nmt_engine() -> NMTEngine:
    """Get or create the singleton NMT engine."""
    global _nmt_engine
    if _nmt_engine is None:
        _nmt_engine = NMTEngine()
    return _nmt_engine
