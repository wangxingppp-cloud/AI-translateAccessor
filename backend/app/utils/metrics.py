"""Performance metrics collection utilities."""
import time
from dataclasses import dataclass, field


@dataclass
class PipelineMetrics:
    """Tracks latency for each stage of the translation pipeline."""

    audio_buffer_ms: float = 0.0
    asr_latency_ms: float = 0.0
    nmt_latency_ms: float = 0.0
    llm_latency_ms: float = 0.0
    total_latency_ms: float = 0.0

    _asr_start: float = field(default=0.0, repr=False)
    _nmt_start: float = field(default=0.0, repr=False)
    _llm_start: float = field(default=0.0, repr=False)
    _pipeline_start: float = field(default=0.0, repr=False)

    def start_pipeline(self) -> None:
        self._pipeline_start = time.perf_counter()

    def start_asr(self) -> None:
        self._asr_start = time.perf_counter()

    def end_asr(self) -> None:
        self.asr_latency_ms = (time.perf_counter() - self._asr_start) * 1000

    def start_nmt(self) -> None:
        self._nmt_start = time.perf_counter()

    def end_nmt(self) -> None:
        self.nmt_latency_ms = (time.perf_counter() - self._nmt_start) * 1000

    def start_llm(self) -> None:
        self._llm_start = time.perf_counter()

    def end_llm(self) -> None:
        self.llm_latency_ms = (time.perf_counter() - self._llm_start) * 1000

    def end_pipeline(self) -> None:
        self.total_latency_ms = (time.perf_counter() - self._pipeline_start) * 1000

    def to_dict(self) -> dict:
        return {
            "audio_buffer_ms": round(self.audio_buffer_ms, 1),
            "asr_latency_ms": round(self.asr_latency_ms, 1),
            "nmt_latency_ms": round(self.nmt_latency_ms, 1),
            "llm_latency_ms": round(self.llm_latency_ms, 1),
            "total_latency_ms": round(self.total_latency_ms, 1),
        }
