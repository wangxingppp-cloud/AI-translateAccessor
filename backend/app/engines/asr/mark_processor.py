"""
Mark types and VAD-based mark generator.

Produces marks on the ring buffer:
  SILENCE  — speech ended (silence > 0.6s), high priority
  PERIODIC — timer fired (every 3s), low priority
  OVERFLOW — buffer near full, force flush
  DRAIN    — session stopping, flush all remaining
"""
import asyncio
from dataclasses import dataclass
from enum import Enum
import numpy as np
from loguru import logger
from .vad_processor import get_vad_processor

TARGET_RATE = 16000
SILENCE_GAP = 0.6
PERIODIC_GAP = 3.0
OVERFLOW_GAP = 25.0  # Trigger when 25s of buffer used


class MarkType(str, Enum):
    SILENCE = "silence"
    PERIODIC = "periodic"
    OVERFLOW = "overflow"
    DRAIN = "drain"


@dataclass
class Mark:
    """A segment of audio to transcribe, identified by global offsets."""
    start: int          # Global sample offset
    end: int            # Global sample offset (exclusive)
    type: MarkType


class MarkGenerator:
    """Analyzes ring buffer content via VAD, produces transcription marks."""

    def __init__(self, ring_buffer):
        self._ring = ring_buffer
        self._vad = get_vad_processor()
        self._marks: asyncio.Queue = asyncio.Queue()
        self._running = False

        # State
        self._in_speech = False
        self._speech_start = 0
        self._silence_dur = 0.0
        self._speech_dur = 0.0
        self._last_checked = 0        # Global sample offset of last VAD check
        self._last_periodic = 0       # Global sample offset of last periodic mark
        self._total_emitted = 0

    @property
    def queue(self) -> asyncio.Queue:
        return self._marks

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    async def run(self) -> None:
        """Background task: poll ring buffer, generate marks."""
        _n = 0
        while self._running:
            await asyncio.sleep(0.05)
            _n += 1
            total = self._ring.total_written
            if _n <= 5:
                logger.info(f"[MARK] Poll #{_n}: total={total}, last_checked={self._last_checked}")
            if total <= self._last_checked:
                continue

            # Read new audio since last check
            new_audio = self._ring.read(self._last_checked, total)
            if len(new_audio) == 0:
                continue

            has_speech = self._vad.process(new_audio)
            chunk_duration = len(new_audio) / TARGET_RATE

            if has_speech:
                if not self._in_speech:
                    # Speech just started
                    self._in_speech = True
                    self._speech_start = self._last_checked
                    self._speech_dur = 0.0
                    self._silence_dur = 0.0

                self._speech_dur += chunk_duration
                self._silence_dur = 0.0

                # Overflow check
                ring_dur = self._ring.available_duration
                if ring_dur >= OVERFLOW_GAP and self._speech_dur >= 3.0:
                    await self._marks.put(Mark(
                        start=self._speech_start, end=total, type=MarkType.OVERFLOW))
                    self._speech_start = total
                    self._speech_dur = 0.0

            elif self._in_speech:
                # Silence during speech
                self._silence_dur += chunk_duration

                if self._silence_dur >= SILENCE_GAP and self._speech_dur >= 0.5:
                    # Sentence boundary
                    await self._marks.put(Mark(
                        start=self._speech_start, end=total, type=MarkType.SILENCE))
                    self._speech_start = total
                    self._speech_dur = 0.0
                    self._silence_dur = 0.0
                    self._in_speech = False
                    self._last_periodic = total
                    self._total_emitted += 1

            # Periodic flush (only if speech is ongoing and no recent mark)
            if self._in_speech and total - self._last_periodic >= PERIODIC_GAP * TARGET_RATE:
                if self._speech_dur >= 1.0:
                    await self._marks.put(Mark(
                        start=self._speech_start, end=total, type=MarkType.PERIODIC))
                    self._speech_start = total
                    self._speech_dur = 0.0
                    self._last_periodic = total
                    self._total_emitted += 1

            self._last_checked = total

        logger.info(f"MarkGenerator stopped ({self._total_emitted} marks emitted)")

    async def drain(self) -> None:
        """Emit DRAIN mark for all remaining unprocessed audio."""
        if self._in_speech and self._speech_dur >= 0.3:
            total = self._ring.total_written
            await self._marks.put(Mark(
                start=self._speech_start, end=total, type=MarkType.DRAIN))
            logger.info(f"DRAIN: {self._speech_start}→{total} ({(total-self._speech_start)/TARGET_RATE:.1f}s)")
