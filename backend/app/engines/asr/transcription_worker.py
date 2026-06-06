"""
Transcription Worker — consumes marks, reads ring buffer, transcribes, sends to frontend.

Runs as a background asyncio task. Each mark triggers:
  1. Read audio from ring buffer at mark.start → mark.end
  2. Transcribe via SenseVoice (to_thread)
  3. Send result to frontend via WebSocket callback
  4. Audio in ring buffer is automatically overwritten (no manual cleanup needed)
"""
import asyncio
import time
from loguru import logger
from .ring_buffer import RingBuffer
from .mark_processor import Mark, MarkType
from .sherpa_engine import ASRResult, get_asr_engine


class TranscriptionWorker:
    """Consumes marks, transcribes, sends to frontend."""

    def __init__(self, ring: RingBuffer, mark_queue: asyncio.Queue, send_callback):
        self._ring = ring
        self._queue = mark_queue
        self._send = send_callback  # async def send(original: str, translated: str, is_final: bool)
        self._engine = get_asr_engine()
        self._running = False
        self._prev_text = ""
        self._total_processed = 0

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    async def run(self) -> None:
        """Main loop: dequeue mark → transcribe → send."""
        while self._running:
            try:
                try:
                    mark = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                self._total_processed += 1
                if self._total_processed <= 3:
                    logger.info(f"[WORKER] Got mark {self._total_processed}: type={mark.type.value}, start={mark.start}, end={mark.end}")
                audio = self._ring.read(mark.start, mark.end)
                dur = len(audio) / 16000
                mark_type = mark.type.value

                if dur < 0.3:
                    if self._total_processed <= 3:
                        logger.info(f"[WORKER] Skip: dur={dur:.2f}s < 0.3")
                    self._queue.task_done()
                    continue
                    self._queue.task_done()
                    continue

                try:
                    result = await asyncio.to_thread(self._engine.transcribe, audio)
                except Exception as e:
                    logger.warning(f"Transcribe failed: {e}")
                    self._queue.task_done()
                    continue

                if result.text and result.text.strip() and result.text != self._prev_text:
                    self._prev_text = result.text
                    logger.info(f"[{mark_type.upper()}] {dur:.1f}s → \"{result.text[:80]}\"")
                    try:
                        await self._send(result.text, dur)
                    except Exception as e:
                        logger.warning(f"Send failed: {e}")

                self._queue.task_done()
            except Exception as e:
                logger.error(f"Worker loop error: {e}")

        logger.info(f"TranscriptionWorker stopped ({self._total_processed} marks processed)")
