"""Correction Engine package.

LLM-based translation correction for post-NMT refinement.
"""
from .corrector import LLMCorrector, CorrectionResult, LLMConfig

__all__ = ["LLMCorrector", "CorrectionResult", "LLMConfig"]
