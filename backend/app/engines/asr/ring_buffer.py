"""
Ring Buffer — fixed 30s circular buffer for audio samples.

Uses global write offset (monotonic counter) so mark positions
remain valid even after the buffer wraps around.
"""
import numpy as np

TARGET_RATE = 16000
BUFFER_SECONDS = 30
CAPACITY = TARGET_RATE * BUFFER_SECONDS  # 480,000 samples


class RingBuffer:
    """Fixed-size circular buffer for float32 audio samples."""

    def __init__(self) -> None:
        self._buf = np.zeros(CAPACITY, dtype=np.float32)
        self._write_pos: int = 0        # Current write position (0..CAPACITY-1)
        self._total_written: int = 0    # Monotonic global sample counter
        self._overflow: bool = False

    def write(self, samples: np.ndarray) -> None:
        """Write samples. Oldest data is overwritten if buffer is full."""
        n = len(samples)
        if n == 0:
            return
        if self._total_written == 0:
            from loguru import logger
            logger.info(f"[RING] First write: {n} samples")
        end = self._write_pos + n
        if end <= CAPACITY:
            self._buf[self._write_pos:end] = samples
        else:
            first = CAPACITY - self._write_pos
            self._buf[self._write_pos:] = samples[:first]
            self._buf[:n - first] = samples[first:]
            self._overflow = True
        self._write_pos = end % CAPACITY
        self._total_written += n

    def read(self, start_offset: int, end_offset: int) -> np.ndarray:
        """Read audio between global offsets. Returns empty array if data overwritten."""
        if start_offset >= end_offset:
            return np.array([], dtype=np.float32)

        available_start = max(0, self._total_written - CAPACITY)
        start = max(start_offset, available_start)
        end = min(end_offset, self._total_written)

        if start >= end:
            return np.array([], dtype=np.float32)

        local_start = start % CAPACITY
        local_end = (end - 1) % CAPACITY + 1

        if local_start < local_end:
            return self._buf[local_start:local_end].copy()
        else:
            return np.concatenate([
                self._buf[local_start:],
                self._buf[:local_end],
            ])

    @property
    def total_written(self) -> int:
        return self._total_written

    @property
    def duration_written(self) -> float:
        return self._total_written / TARGET_RATE

    @property
    def available_duration(self) -> float:
        return min(self.duration_written, BUFFER_SECONDS)
