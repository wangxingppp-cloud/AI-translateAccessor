"""
LLM-based translation correction engine.

After NMT produces a fast initial translation, this engine sends the
text to an LLM for refinement. It uses the provider configuration
sent by the frontend (provider, apiKey, model, baseUrl).

Supported providers:
  - openai    → OpenAI API (gpt-4o, gpt-4o-mini, etc.)
  - anthropic → Anthropic API (claude-sonnet-4-6, claude-haiku-4-5, etc.)
  - deepseek  → DeepSeek API (OpenAI-compatible)
  - custom    → Custom OpenAI-compatible endpoint (Ollama, vLLM, etc.)

The correction is asynchronous — NMT result is sent immediately,
LLM correction arrives 1-3 seconds later as a subtitle_corrected message.
"""
import time
from dataclasses import dataclass, field
from typing import Optional

from loguru import logger


@dataclass
class CorrectionResult:
    """Result from LLM translation correction."""
    original: str                     # Source text (English)
    draft: str                        # NMT initial translation
    corrected: str                    # LLM-corrected translation
    diff_segments: list[dict] = field(default_factory=list)  # For UI highlighting
    latency_ms: float = 0.0
    model: str = ""


@dataclass
class LLMConfig:
    """LLM provider configuration (mirrors frontend LLMConfig)."""
    provider: str = "openai"          # openai | anthropic | deepseek | custom
    api_key: str = ""
    model: str = "gpt-4o-mini"
    base_url: str = ""
    enabled: bool = False


class LLMCorrector:
    """
    LLM-based translation corrector with multi-provider support.

    Usage:
        config = LLMConfig(provider="openai", api_key="sk-...", model="gpt-4o-mini")
        corrector = LLMCorrector(config)
        result = await corrector.correct(
            original="Hello world",
            draft="你好世界",
            context=[...]
        )
    """

    CORRECTION_PROMPT = """You are a professional simultaneous interpreter. Refine the machine translation below.

Rules:
1. Terminology: If the context mentions specific terms, use them consistently.
2. Context coherence: Make the translation flow naturally with previous sentences.
3. Fluency: Use natural, spoken-style Chinese suitable for subtitles.
4. Brevity: Keep it concise — same length as the original or shorter.
5. Minimal change: Only fix what needs fixing. Keep good parts unchanged.

Previous context:
{context}

Source (English): {original}
Machine translation (draft): {draft}

Output ONLY the corrected Chinese translation. No explanations, no quotes, no prefixes."""

    def __init__(self, config: LLMConfig) -> None:
        self._config = config
        self._client = None  # Lazy-initialized API client

    async def correct(
        self,
        original: str,
        draft: str,
        context: list[tuple[str, str]] | None = None,
    ) -> CorrectionResult:
        """Correct a machine translation using the configured LLM.

        Args:
            original: The source text (English).
            draft: The NMT initial translation.
            context: List of (source, translation) tuples for recent sentences.

        Returns:
            CorrectionResult with corrected text and diff segments.
        """
        start = time.perf_counter()

        if not self._config.enabled or not self._config.api_key:
            return CorrectionResult(
                original=original,
                draft=draft,
                corrected=draft,
                latency_ms=0,
                model="disabled",
            )

        if not original.strip() or not draft.strip():
            return CorrectionResult(
                original=original,
                draft=draft,
                corrected=draft,
                latency_ms=0,
            )

        try:
            ctx_text = self._build_context(context)
            prompt = self.CORRECTION_PROMPT.format(
                context=ctx_text or "(no previous context)",
                original=original,
                draft=draft,
            )
            corrected = await self._call_llm(prompt)
            corrected = corrected.strip() or draft

            # Compute diff segments for UI highlighting
            diff = self._compute_diff(draft, corrected)

            latency = (time.perf_counter() - start) * 1000

            return CorrectionResult(
                original=original,
                draft=draft,
                corrected=corrected,
                diff_segments=diff,
                latency_ms=round(latency, 1),
                model=self._config.model,
            )

        except Exception as e:
            logger.warning(f"LLM correction failed ({self._config.provider}): {e}")
            return CorrectionResult(
                original=original,
                draft=draft,
                corrected=draft,  # Fall back to NMT result
                latency_ms=(time.perf_counter() - start) * 1000,
            )

    async def _call_llm(self, prompt: str) -> str:
        """Route the correction request to the appropriate provider."""
        provider = self._config.provider

        if provider in ("openai", "deepseek", "custom"):
            return await self._call_openai_compatible(prompt)
        elif provider == "anthropic":
            return await self._call_anthropic(prompt)
        else:
            raise ValueError(f"Unknown provider: {provider}")

    async def _call_openai_compatible(self, prompt: str) -> str:
        """Call OpenAI-compatible chat API (OpenAI, DeepSeek, custom)."""
        try:
            from openai import AsyncOpenAI
        except ImportError:
            logger.warning("openai package not installed. pip install openai")
            return ""

        if self._client is None or not isinstance(self._client, AsyncOpenAI):
            base = self._config.base_url or "https://api.openai.com/v1"
            self._client = AsyncOpenAI(
                api_key=self._config.api_key,
                base_url=base,
                timeout=30.0,
            )

        response = await self._client.chat.completions.create(
            model=self._config.model,
            messages=[
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=500,
        )

        return response.choices[0].message.content or ""

    async def _call_anthropic(self, prompt: str) -> str:
        """Call Anthropic Messages API."""
        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            logger.warning("anthropic package not installed. pip install anthropic")
            return ""

        if self._client is None or not hasattr(self._client, 'messages'):
            base = self._config.base_url or "https://api.anthropic.com"
            self._client = AsyncAnthropic(
                api_key=self._config.api_key,
                base_url=base,
                timeout=30.0,
            )

        response = await self._client.messages.create(
            model=self._config.model,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )

        # Claude returns list of content blocks
        content = response.content
        if isinstance(content, list) and len(content) > 0:
            return getattr(content[0], 'text', str(content[0]))
        return str(content)

    # ── Helpers ────────────────────────────────────────────────

    @staticmethod
    def _build_context(context: list[tuple[str, str]] | None) -> str:
        """Format translation context for the prompt."""
        if not context:
            return ""
        lines = []
        for i, (src, tgt) in enumerate(context[-5:]):  # Last 5 entries
            lines.append(f"[{i+1}] EN: {src}")
            lines.append(f"    ZH: {tgt}")
        return "\n".join(lines)

    @staticmethod
    def _compute_diff(draft: str, corrected: str) -> list[dict]:
        """Compute a simple word-level diff for UI highlighting."""
        if draft == corrected:
            return [{"type": "unchanged", "text": corrected}]

        # Simple heuristic: if the corrected text is a slight modification,
        # show the diff as deleted + inserted
        # For a more sophisticated diff, use difflib in the future
        if len(corrected) < len(draft) * 1.5 and len(corrected) > len(draft) * 0.5:
            # Similar length — try to find common prefix/suffix
            from difflib import SequenceMatcher
            sm = SequenceMatcher(None, draft, corrected)
            segments = []
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag == 'equal':
                    segments.append({"type": "unchanged", "text": draft[i1:i2]})
                elif tag == 'replace':
                    segments.append({"type": "deleted", "text": draft[i1:i2]})
                    segments.append({"type": "inserted", "text": corrected[j1:j2]})
                elif tag == 'delete':
                    segments.append({"type": "deleted", "text": draft[i1:i2]})
                elif tag == 'insert':
                    segments.append({"type": "inserted", "text": corrected[j1:j2]})
            return segments

        # Completely different — show full replacement
        return [
            {"type": "deleted", "text": draft},
            {"type": "inserted", "text": corrected},
        ]
