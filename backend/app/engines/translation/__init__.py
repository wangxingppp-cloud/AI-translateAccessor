"""
Translation Engine package.

Provides NMT (MarianMT) and LLM-based translation capabilities.
- NMTEngine: Fast local translation (MarianMT)
- TranslationContext: Sliding window of recent translations
- HybridTranslator: Combines NMT + LLM (future module)
"""
from .nmt_engine import NMTEngine, NMTResult, get_nmt_engine
from .context_manager import TranslationContext, ContextEntry

__all__ = [
    "NMTEngine",
    "NMTResult",
    "get_nmt_engine",
    "TranslationContext",
    "ContextEntry",
]
