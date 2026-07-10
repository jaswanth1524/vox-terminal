from __future__ import annotations

import math
import threading
from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class LatencySample:
    engine: str
    audio_ms: float
    finalize_ms: float
    inference_ms: float
    postprocess_ms: float
    paste_ms: float
    total_ms: float


class LatencyHistory:
    def __init__(self, max_size: int = 100) -> None:
        self._samples: deque[LatencySample] = deque(maxlen=max_size)
        self._lock = threading.Lock()

    def add(self, sample: LatencySample) -> None:
        with self._lock:
            self._samples.append(sample)

    def samples(self) -> tuple[LatencySample, ...]:
        with self._lock:
            return tuple(self._samples)

    def render(self) -> str:
        samples = self.samples()
        if not samples:
            return "No latency samples yet."
        totals = sorted(sample.total_ms for sample in samples)
        inference = sorted(sample.inference_ms for sample in samples)
        return "\n".join(
            [
                f"Samples: {len(samples)}",
                f"Release-to-paste p50: {_percentile(totals, 50):.0f} ms",
                f"Release-to-paste p95: {_percentile(totals, 95):.0f} ms",
                f"Inference p50: {_percentile(inference, 50):.0f} ms",
                f"Inference p95: {_percentile(inference, 95):.0f} ms",
                f"Latest engine: {samples[-1].engine}",
            ]
        )


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    index = max(0, math.ceil(percentile / 100 * len(values)) - 1)
    return values[index]
