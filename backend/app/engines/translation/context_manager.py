"""
Translation context manager.

Maintains a sliding window of recent translations for LLM context.
Used by both the NMT pipeline (for reference) and LLM correction
(to understand preceding sentences).
"""
from collections import deque
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ContextEntry:
    """A single entry in the translation context."""
    source: str                       # Original source text
    target: str                       # Translated text
    sequence_id: str                  # Unique identifier
    timestamp: float                  # Unix timestamp


class TranslationContext:
    """
    Sliding window of recent translation pairs.

    Provides context for LLM correction so the model can:
      - Maintain terminology consistency
      - Keep pronoun/gender agreement across sentences
      - Produce coherent multi-sentence output
    """

    def __init__(self, max_entries: int = 8) -> None:
        self._entries: deque[ContextEntry] = deque(maxlen=max_entries)
        self._max_entries = max_entries

    def add(self, source: str, target: str, sequence_id: str, timestamp: float) -> None:
        """Record a new translation pair."""
        self._entries.append(
            ContextEntry(
                source=source,
                target=target,
                sequence_id=sequence_id,
                timestamp=timestamp,
            )
        )

    def get_recent(self, n: int = 5) -> list[ContextEntry]:
        """Get the N most recent entries."""
        entries = list(self._entries)
        return entries[-n:] if len(entries) > n else entries

    def get_as_text(self, n: int = 5) -> str:
        """Get recent entries formatted as a context string for LLM prompts."""
        recent = self.get_recent(n)
        if not recent:
            return ""

        lines = []
        for i, entry in enumerate(recent):
            lines.append(f"[{i+1}] 原文: {entry.source}")
            lines.append(f"    译文: {entry.target}")
        return "\n".join(lines)

    def clear(self) -> None:
        """Clear all context entries."""
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)

    @property
    def is_empty(self) -> bool:
        return len(self._entries) == 0
