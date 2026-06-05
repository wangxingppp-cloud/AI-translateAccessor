"""
ASR Engine package.

Provides streaming speech recognition via sherpa-onnx + Paraformer.
- SherpaASREngine: Core recognizer (singleton)
- VadProcessor: Voice Activity Detection (singleton)
- StreamHandler: Per-session audio→text pipeline
"""
from .sherpa_engine import SherpaASREngine, ASRResult, get_asr_engine
from .vad_processor import VadProcessor, get_vad_processor
from .stream_handler import StreamHandler

__all__ = [
    "SherpaASREngine",
    "ASRResult",
    "get_asr_engine",
    "VadProcessor",
    "get_vad_processor",
    "StreamHandler",
]
