"""
Translation Engine package.

Provides LLM-based translation and context management.
- TranslationContext: Sliding window of recent translations
"""
from .context_manager import TranslationContext, ContextEntry

__all__ = [
    "TranslationContext",
    "ContextEntry",
]
