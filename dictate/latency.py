from __future__ import annotations

import json
import logging
import math
import os
import tempfile
import threading
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


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
    def __init__(
        self,
        max_size: int = 100,
        *,
        storage_path: Path | None = None,
    ) -> None:
        self._samples: deque[LatencySample] = deque(maxlen=max_size)
        self._lock = threading.Lock()
        self._storage_path = storage_path
        if storage_path is not None:
            self._load()

    def add(self, sample: LatencySample) -> None:
        with self._lock:
            self._samples.append(sample)
            self._persist()

    def samples(self) -> tuple[LatencySample, ...]:
        with self._lock:
            return tuple(self._samples)

    def clear(self) -> None:
        with self._lock:
            self._samples.clear()
            if self._storage_path is None:
                return
            try:
                self._storage_path.unlink(missing_ok=True)
            except OSError as exc:
                logging.warning("Could not clear latency data: %s", exc)

    def render(self) -> str:
        samples = self.samples()
        if not samples:
            return "No latency samples yet."
        totals = sorted(sample.total_ms for sample in samples)
        inference = sorted(sample.inference_ms for sample in samples)
        lines = [
            f"Samples: {len(samples)}",
            f"Release-to-paste p50: {_percentile(totals, 50):.0f} ms",
            f"Release-to-paste p95: {_percentile(totals, 95):.0f} ms",
            f"Inference p50: {_percentile(inference, 50):.0f} ms",
            f"Inference p95: {_percentile(inference, 95):.0f} ms",
            "",
            "By engine:",
        ]
        for engine in sorted({sample.engine for sample in samples}):
            engine_samples = [sample for sample in samples if sample.engine == engine]
            engine_totals = sorted(sample.total_ms for sample in engine_samples)
            engine_inference = sorted(sample.inference_ms for sample in engine_samples)
            lines.append(
                f"{engine} ({len(engine_samples)}): total p50/p95 "
                f"{_percentile(engine_totals, 50):.0f}/{_percentile(engine_totals, 95):.0f} ms; "
                f"inference p50/p95 {_percentile(engine_inference, 50):.0f}/"
                f"{_percentile(engine_inference, 95):.0f} ms"
            )
        lines.extend(["", f"Latest engine: {samples[-1].engine}"])
        return "\n".join(lines)

    def _load(self) -> None:
        if self._storage_path is None or not self._storage_path.exists():
            return
        try:
            payload = json.loads(self._storage_path.read_text(encoding="utf-8"))
            raw_samples = payload.get("samples", [])
            if payload.get("version") != 1 or not isinstance(raw_samples, list):
                raise ValueError("unsupported latency data format")
            for raw_sample in raw_samples:
                self._samples.append(_parse_sample(raw_sample))
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            self._samples.clear()
            logging.warning("Ignoring invalid latency data in %s: %s", self._storage_path, exc)

    def _persist(self) -> None:
        if self._storage_path is None:
            return
        try:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{self._storage_path.name}.",
                suffix=".tmp",
                dir=self._storage_path.parent,
            )
            temporary_path = Path(temporary_name)
            try:
                payload = {
                    "version": 1,
                    "samples": [asdict(sample) for sample in self._samples],
                }
                with os.fdopen(descriptor, "w", encoding="utf-8") as data_file:
                    json.dump(payload, data_file, separators=(",", ":"))
                    data_file.flush()
                    os.fsync(data_file.fileno())
                os.replace(temporary_path, self._storage_path)
            finally:
                temporary_path.unlink(missing_ok=True)
        except OSError as exc:
            logging.warning("Could not persist latency data: %s", exc)


def _parse_sample(raw_sample: Any) -> LatencySample:
    if not isinstance(raw_sample, dict):
        raise ValueError("latency sample must be an object")
    engine = raw_sample.get("engine")
    if not isinstance(engine, str) or not engine:
        raise ValueError("latency sample engine must be a non-empty string")
    values: dict[str, float] = {}
    for field_name in (
        "audio_ms",
        "finalize_ms",
        "inference_ms",
        "postprocess_ms",
        "paste_ms",
        "total_ms",
    ):
        value = raw_sample.get(field_name)
        if (
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not math.isfinite(value)
            or value < 0
        ):
            raise ValueError(f"latency sample {field_name} must be a finite non-negative number")
        values[field_name] = float(value)
    return LatencySample(engine=engine, **values)


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    index = max(0, math.ceil(percentile / 100 * len(values)) - 1)
    return values[index]
