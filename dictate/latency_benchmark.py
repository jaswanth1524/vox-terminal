from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass

import numpy as np

from .engines import TranscriptionEngine


@dataclass(frozen=True)
class BenchmarkCase:
    text: str
    audio: np.ndarray


@dataclass(frozen=True)
class EngineBenchmark:
    engine: str
    samples_ms: tuple[float, ...]
    word_error_rate: float
    hypotheses: tuple[str, ...] = ()

    @property
    def p50_ms(self) -> float:
        return percentile(self.samples_ms, 50)

    @property
    def p95_ms(self) -> float:
        return percentile(self.samples_ms, 95)


def benchmark_engine(
    engine: TranscriptionEngine,
    cases: list[BenchmarkCase],
) -> EngineBenchmark:
    engine.load()
    samples: list[float] = []
    edits = 0
    reference_words = 0
    hypotheses: list[str] = []
    for case in cases:
        started = time.perf_counter_ns()
        hypothesis = engine.transcribe(case.audio)
        hypotheses.append(hypothesis)
        samples.append((time.perf_counter_ns() - started) / 1_000_000)
        reference = _words(case.text)
        edits += _edit_distance(reference, _words(hypothesis))
        reference_words += len(reference)
    return EngineBenchmark(
        engine=engine.name,
        samples_ms=tuple(samples),
        word_error_rate=edits / max(1, reference_words),
        hypotheses=tuple(hypotheses),
    )


def should_promote_parakeet(
    whisper: EngineBenchmark,
    parakeet: EngineBenchmark,
) -> bool:
    """Return whether Parakeet also stays within two WER points of Whisper."""

    return (
        meets_fast_default_gate(whisper, parakeet)
        and parakeet.word_error_rate <= whisper.word_error_rate + 0.02
    )


def meets_fast_default_gate(
    whisper: EngineBenchmark,
    parakeet: EngineBenchmark,
) -> bool:
    """Return whether Parakeet is suitable as the latency-first English default."""

    return (
        parakeet.p50_ms <= 500
        and parakeet.p95_ms <= 750
        and parakeet.p95_ms < whisper.p95_ms
        and parakeet.word_error_rate <= 0.15
    )


def percentile(values: tuple[float, ...], target: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(target / 100 * len(ordered)) - 1)
    return ordered[index]


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)?", text.casefold())


def _edit_distance(reference: list[str], hypothesis: list[str]) -> int:
    previous = list(range(len(hypothesis) + 1))
    for row, reference_word in enumerate(reference, start=1):
        current = [row]
        for column, hypothesis_word in enumerate(hypothesis, start=1):
            current.append(
                min(
                    current[column - 1] + 1,
                    previous[column] + 1,
                    previous[column - 1] + (reference_word != hypothesis_word),
                )
            )
        previous = current
    return previous[-1]
