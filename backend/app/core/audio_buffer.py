"""
Ring buffer for real-time audio chunk processing.

Thread-safe circular buffer designed for 16-bit PCM audio chunks
at 16 kHz, single channel, with configurable chunk duration.
"""
import threading
import numpy as np


class AudioRingBuffer:
    """
    Fixed-size ring buffer for audio chunks.

    Each chunk is a fixed-size numpy array (float32, shape: (chunk_samples,)).
    The buffer overwrites oldest data when full.

    Chunk size = sample_rate * chunk_duration_seconds
    e.g. 16000 * 0.200 = 3200 samples per chunk
    """

    def __init__(self, capacity: int = 100) -> None:
        self._capacity = capacity
        self._buffer: list[np.ndarray | None] = [None] * capacity
        self._write_idx = 0
        self._read_idx = 0
        self._count = 0
        self._lock = threading.Lock()

    def put(self, chunk: np.ndarray) -> None:
        """Write a chunk to the buffer (overwrites oldest if full).

        Args:
            chunk: float32 numpy array of audio samples.
        """
        with self._lock:
            self._buffer[self._write_idx] = chunk.copy()
            self._write_idx = (self._write_idx + 1) % self._capacity
            if self._count == self._capacity:
                self._read_idx = (self._read_idx + 1) % self._capacity
            else:
                self._count += 1

    def get(self) -> np.ndarray | None:
        """Read and remove the oldest chunk from the buffer.

        Returns:
            Chunk as float32 numpy array, or None if buffer is empty.
        """
        with self._lock:
            if self._count == 0:
                return None
            chunk = self._buffer[self._read_idx]
            self._buffer[self._read_idx] = None
            self._read_idx = (self._read_idx + 1) % self._capacity
            self._count -= 1
            return chunk

    def peek(self, n: int = 1) -> list[np.ndarray]:
        """Peek at the next `n` chunks without removing them."""
        with self._lock:
            result = []
            for i in range(min(n, self._count)):
                idx = (self._read_idx + i) % self._capacity
                chunk = self._buffer[idx]
                if chunk is not None:
                    result.append(chunk)
            return result

    @property
    def count(self) -> int:
        """Number of chunks currently in the buffer."""
        with self._lock:
            return self._count

    @property
    def is_empty(self) -> bool:
        return self.count == 0

    def clear(self) -> None:
        """Empty the buffer."""
        with self._lock:
            self._buffer = [None] * self._capacity
            self._write_idx = 0
            self._read_idx = 0
            self._count = 0

    def __len__(self) -> int:
        return self.count
