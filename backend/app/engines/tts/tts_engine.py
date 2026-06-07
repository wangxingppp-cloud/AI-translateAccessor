"""
TTS Engine — sherpa-onnx ZipVoice offline text-to-speech.

Uses the ZipVoice INT8 model for Chinese/English zero-shot speech synthesis.
Requires: encoder.int8.onnx, decoder.int8.onnx, vocos_24khz.onnx,
          lexicon.txt, tokens.txt, espeak-ng-data/, test_wavs/ (reference)
"""
import asyncio
import time
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
from loguru import logger

from ...config import get_settings


class TTSEngine:
    """sherpa-onnx ZipVoice TTS engine — singleton shared across sessions."""

    def __init__(self) -> None:
        settings = get_settings()
        model_dir = Path(settings.tts_model_path) if settings.tts_model_path else \
            settings.resolved_models_dir / "sherpa-onnx-zipvoice-distill-int8-zh-en-emilia"

        self._sample_rate = 24000
        self._engine = None
        self._ready = False
        self._ref_audio_list: list = []     # pre-converted Python list
        self._ref_sr: int = 24000
        self._ref_text: str = ""

        if not model_dir.exists():
            logger.warning(f"TTS model not found at {model_dir}")
            return

        encoder = self._find_file(model_dir, "encoder", ".onnx")
        decoder = self._find_file(model_dir, "decoder", ".onnx")
        tokens = model_dir / "tokens.txt"
        lexicon = model_dir / "lexicon.txt"
        data_dir = model_dir / "espeak-ng-data"
        vocoder = settings.resolved_models_dir / "vocos_24khz.onnx"

        if not (encoder and decoder and tokens.exists() and data_dir.exists() and vocoder.exists()):
            missing = []
            if not encoder: missing.append("encoder*.onnx")
            if not decoder: missing.append("decoder*.onnx")
            if not tokens.exists(): missing.append("tokens.txt")
            if not data_dir.exists(): missing.append("espeak-ng-data/")
            if not vocoder.exists(): missing.append("vocos_24khz.onnx")
            logger.error(f"TTS model files incomplete in {model_dir}, missing: {missing}")
            return

        # Load default reference audio from test_wavs
        self._load_reference(model_dir)

        try:
            import sherpa_onnx

            zipvoice_cfg = sherpa_onnx.OfflineTtsZipvoiceModelConfig(
                tokens=str(tokens),
                encoder=str(encoder),
                decoder=str(decoder),
                vocoder=str(vocoder),
                data_dir=str(data_dir),
                lexicon=str(lexicon) if lexicon.exists() else "",
            )

            model_cfg = sherpa_onnx.OfflineTtsModelConfig(
                zipvoice=zipvoice_cfg,
                num_threads=settings.tts_num_threads,
                provider="cpu",
            )

            tts_cfg = sherpa_onnx.OfflineTtsConfig(model=model_cfg)

            if not tts_cfg.validate():
                logger.error("TTS config validation failed")
                return

            self._engine = sherpa_onnx.OfflineTts(tts_cfg)
            self._sample_rate = self._engine.sample_rate
            self._ready = True
            logger.info(f"TTS engine ready: ZipVoice INT8, {self._sample_rate}Hz")

        except Exception as e:
            logger.error(f"TTS engine init failed: {e}")
            self._engine = None

    def _load_reference(self, model_dir: Path) -> None:
        """Load default reference audio from model's test_wavs directory."""
        try:
            import soundfile as sf

            test_wavs = model_dir / "test_wavs"
            if not test_wavs.exists():
                logger.warning("No test_wavs directory for reference audio")
                return

            wav_files = sorted(test_wavs.glob("*.wav"))
            if not wav_files:
                logger.warning("No .wav files in test_wavs for reference")
                return

            ref_path = wav_files[0]
            ref_audio, self._ref_sr = sf.read(str(ref_path))
            self._ref_audio_list = ref_audio.tolist()  # pre-convert once
            self._ref_text = "那还是三十六年前, 一九八七年. 我呢考上了武汉大学的计算机系."
            logger.info(f"TTS reference: {ref_path.name} ({len(self._ref_audio_list)} samples, {self._ref_sr}Hz)")

        except Exception as e:
            logger.warning(f"Failed to load reference audio: {e}")

    def synthesize(self, text: str, sid: int = 0) -> Tuple[np.ndarray, int]:
        """Synthesize speech from text. Returns (float32_samples, sample_rate)."""
        if not self._ready or self._engine is None:
            raise RuntimeError("TTS engine not ready")

        import sherpa_onnx

        start = time.perf_counter()
        has_ref = len(self._ref_audio_list) > 0

        gen_config = sherpa_onnx.GenerationConfig()
        gen_config.sid = 0
        gen_config.num_steps = 4
        gen_config.speed = 1.0

        if has_ref:
            gen_config.reference_audio = self._ref_audio_list
            gen_config.reference_sample_rate = self._ref_sr
            gen_config.reference_text = self._ref_text

        audio = self._engine.generate(text, gen_config)
        elapsed = (time.perf_counter() - start) * 1000
        logger.info(f"[TTS] '{text[:30]}' → {len(audio.samples)} samples ({elapsed:.0f}ms)")

        if len(audio.samples) == 0:
            logger.warning("[TTS] empty result, retrying without reference")
            gen_config2 = sherpa_onnx.GenerationConfig()
            gen_config2.num_steps = 4
            audio = self._engine.generate(text, gen_config2)

        return np.array(audio.samples, dtype=np.float32), audio.sample_rate

    async def synthesize_async(self, text: str, sid: int = 0) -> Tuple[np.ndarray, int]:
        """Non-blocking synthesis — runs in thread executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.synthesize, text, sid)

    def is_ready(self) -> bool:
        return self._ready

    @staticmethod
    def _find_file(model_dir: Path, stem: str, suffix: str) -> Optional[str]:
        for pattern in [f"*{stem}*int8*{suffix}", f"*{stem}*{suffix}"]:
            candidates = list(model_dir.glob(pattern))
            if candidates:
                return str(candidates[0])
        return None


_engine: Optional[TTSEngine] = None


def get_tts_engine() -> TTSEngine:
    global _engine
    if _engine is None:
        _engine = TTSEngine()
    return _engine
