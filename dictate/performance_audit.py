from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import tempfile
import time
import wave
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import numpy as np

from .config import DEFAULT_PARAKEET_BEAM_SIZE, load_config
from .engines import TranscriptionEngine, build_engine
from .latency_benchmark import BenchmarkCase, percentile

P50_BUDGET_MS = 500.0
P95_BUDGET_MS = 750.0
PEAK_MEMORY_BUDGET_BYTES = round(1.5 * 1024**3)
MEMORY_GROWTH_BUDGET_BYTES = 100 * 1024 * 1024
BUNDLE_SIZE_BUDGET_BYTES = 300 * 1024 * 1024
LATENCY_SAMPLE_LIMIT = 20

AUDIT_PHRASES = (
    "Open the terminal and run the test suite.",
    "Create a new branch for the latency improvements.",
    "Vox Terminal keeps every recording on this Mac.",
    "Check CPU memory and network usage before deploying.",
    "Finish the report and paste the final result.",
)

ClockNs = Callable[[], int]
MemoryReader = Callable[[], int]


@dataclass(frozen=True)
class PerformanceAudit:
    engine: str
    iterations: int
    latency_iterations: int
    load_ms: float
    p50_ms: float
    p95_ms: float
    peak_memory_bytes: int
    memory_growth_bytes: int
    bundle_size_bytes: int | None
    gates: dict[str, bool]

    @property
    def passed(self) -> bool:
        return all(self.gates.values())

    def to_dict(self) -> dict[str, object]:
        return {**asdict(self), "passed": self.passed}


def audit_engine(
    engine: TranscriptionEngine,
    cases: Sequence[BenchmarkCase],
    *,
    iterations: int = 100,
    bundle_path: Path | None = None,
    clock_ns: ClockNs = time.perf_counter_ns,
    memory_reader: MemoryReader | None = None,
) -> PerformanceAudit:
    if not cases:
        raise ValueError("performance audit requires at least one case")
    if iterations <= 0:
        raise ValueError("iterations must be positive")
    memory_reader = memory_reader or physical_memory_bytes

    load_started = clock_ns()
    engine.load()
    load_ms = (clock_ns() - load_started) / 1_000_000
    memory_after_load = memory_reader()

    samples_ms: list[float] = []
    observed_peak = memory_after_load
    latency_iterations = min(iterations, LATENCY_SAMPLE_LIMIT)
    memory_sample_stride = max(1, iterations // 10)
    for index in range(iterations):
        case = cases[index % len(cases)]
        started = clock_ns()
        engine.transcribe(case.audio)
        elapsed_ms = (clock_ns() - started) / 1_000_000
        if index < latency_iterations:
            samples_ms.append(elapsed_ms)
        if (index + 1) % memory_sample_stride == 0:
            observed_peak = max(observed_peak, memory_reader())

    memory_after_soak = memory_reader()
    peak_memory = max(observed_peak, memory_after_soak)
    bundle_size = directory_size(bundle_path) if bundle_path and bundle_path.exists() else None
    p50_ms = percentile(tuple(samples_ms), 50)
    p95_ms = percentile(tuple(samples_ms), 95)
    memory_growth = max(0, memory_after_soak - memory_after_load)
    gates = {
        "p50": p50_ms <= P50_BUDGET_MS,
        "p95": p95_ms <= P95_BUDGET_MS,
        "peak_memory": peak_memory <= PEAK_MEMORY_BUDGET_BYTES,
        "memory_growth": memory_growth <= MEMORY_GROWTH_BUDGET_BYTES,
    }
    if bundle_path is not None:
        gates["bundle_size"] = (
            bundle_size is not None and bundle_size <= BUNDLE_SIZE_BUDGET_BYTES
        )
    return PerformanceAudit(
        engine=engine.name,
        iterations=iterations,
        latency_iterations=latency_iterations,
        load_ms=load_ms,
        p50_ms=p50_ms,
        p95_ms=p95_ms,
        peak_memory_bytes=peak_memory,
        memory_growth_bytes=memory_growth,
        bundle_size_bytes=bundle_size,
        gates=gates,
    )


def current_rss_bytes() -> int:
    result = subprocess.run(
        ["/bin/ps", "-o", "rss=", "-p", str(os.getpid())],
        check=True,
        capture_output=True,
        text=True,
    )
    return int(result.stdout.strip()) * 1024


def physical_memory_bytes() -> int:
    if platform.system() != "Darwin":
        return current_rss_bytes()
    result = subprocess.run(
        ["/usr/bin/vmmap", "-summary", str(os.getpid())],
        check=True,
        capture_output=True,
        text=True,
    )
    for line in result.stdout.splitlines():
        if line.startswith("Physical footprint:"):
            return _parse_memory_size(line.partition(":")[2].strip())
    raise RuntimeError("vmmap did not report a physical footprint")


def _parse_memory_size(value: str) -> int:
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)([KMG])", value)
    if match is None:
        raise ValueError(f"Unsupported memory size: {value}")
    multipliers = {"K": 1024, "M": 1024**2, "G": 1024**3}
    return round(float(match.group(1)) * multipliers[match.group(2)])


def directory_size(path: Path) -> int:
    total = 0
    seen_files: set[tuple[int, int]] = set()
    for item in path.rglob("*"):
        metadata = item.lstat()
        if item.is_symlink():
            total += metadata.st_size
            continue
        if not item.is_file():
            continue
        identity = (metadata.st_dev, metadata.st_ino)
        if identity in seen_files:
            continue
        seen_files.add(identity)
        total += metadata.st_size
    return total


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit local dictation latency, memory, and app bundle size"
    )
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument(
        "--app-path",
        type=Path,
        default=Path("dist/Vox Terminal.app"),
    )
    parser.add_argument("--voice", default="Samantha")
    parser.add_argument("--rate", type=int, default=190)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    config = load_config()
    engine = build_engine(
        replace(
            config,
            engine="parakeet",
            parakeet_beam_size=DEFAULT_PARAKEET_BEAM_SIZE,
        )
    )
    with tempfile.TemporaryDirectory(prefix="vox-performance-") as temp_dir:
        cases = _synthesize_cases(Path(temp_dir), voice=args.voice, rate=args.rate)
        audit = audit_engine(
            engine,
            cases,
            iterations=args.iterations,
            bundle_path=args.app_path,
        )

    if args.json:
        print(json.dumps(audit.to_dict(), indent=2, sort_keys=True))
    else:
        bundle = (
            f"{audit.bundle_size_bytes / (1024 * 1024):.0f} MiB"
            if audit.bundle_size_bytes is not None
            else "not measured"
        )
        print(
            f"{audit.engine}: load={audit.load_ms:.0f}ms "
            f"p50={audit.p50_ms:.0f}ms p95={audit.p95_ms:.0f}ms "
            f"peak_memory={audit.peak_memory_bytes / (1024 * 1024):.0f}MiB "
            f"growth={audit.memory_growth_bytes / (1024 * 1024):.0f}MiB "
            f"bundle={bundle}"
        )
        for gate, passed in audit.gates.items():
            print(f"{'PASS' if passed else 'FAIL'} {gate}")
    return 0 if audit.passed else 1


def _synthesize_cases(directory: Path, *, voice: str, rate: int) -> list[BenchmarkCase]:
    cases: list[BenchmarkCase] = []
    for index, phrase in enumerate(AUDIT_PHRASES):
        path = directory / f"case-{index:02d}.wav"
        subprocess.run(
            [
                "say",
                "-v",
                voice,
                "-r",
                str(rate),
                "-o",
                str(path),
                "--file-format=WAVE",
                "--data-format=LEI16@16000",
                phrase,
            ],
            check=True,
            capture_output=True,
        )
        cases.append(BenchmarkCase(phrase, _read_wav(path)))
    return cases


def _read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as audio_file:
        channels = audio_file.getnchannels()
        width = audio_file.getsampwidth()
        rate = audio_file.getframerate()
        frames = audio_file.readframes(audio_file.getnframes())
    if channels != 1 or width != 2 or rate != 16_000:
        raise ValueError(f"Unexpected audit audio format: {channels=} {width=} {rate=}")
    return np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32_768.0


if __name__ == "__main__":
    raise SystemExit(main())
