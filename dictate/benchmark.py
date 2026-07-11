from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .network import install_runtime_network_policy

# Benchmarks exercise exactly the same offline network policy as the app.
install_runtime_network_policy()

from .config import DEFAULT_MODEL, DEFAULT_PARAKEET_MODEL, load_config  # noqa: E402
from .mel import install_parakeet_librosa_shim  # noqa: E402
from .transcriber import Transcriber  # noqa: E402

Clock = Callable[[], float]
ParakeetLoader = Callable[[str], Any]


@dataclass(frozen=True)
class BenchmarkResult:
    engine: str
    model: str
    load_seconds: float
    transcribe_seconds: float
    text: str

    @property
    def total_seconds(self) -> float:
        return self.load_seconds + self.transcribe_seconds

    def to_dict(self) -> dict[str, str | float]:
        return {
            "engine": self.engine,
            "model": self.model,
            "load_seconds": round(self.load_seconds, 4),
            "transcribe_seconds": round(self.transcribe_seconds, 4),
            "total_seconds": round(self.total_seconds, 4),
            "text": self.text,
        }


def benchmark_whisper(
    audio_path: Path,
    *,
    model: str = DEFAULT_MODEL,
    language: str = "en",
    clock: Clock = time.perf_counter,
    transcriber: Transcriber | None = None,
) -> BenchmarkResult:
    transcriber = transcriber or Transcriber(
        model=model,
        language=language,
        offline=True,
    )
    load_start = clock()
    transcriber.load()
    load_seconds = clock() - load_start

    transcribe_start = clock()
    text = transcriber.transcribe(str(audio_path))
    transcribe_seconds = clock() - transcribe_start
    return BenchmarkResult(
        engine="whisper",
        model=model,
        load_seconds=load_seconds,
        transcribe_seconds=transcribe_seconds,
        text=text.strip(),
    )


def benchmark_parakeet(
    audio_path: Path,
    *,
    model: str = DEFAULT_PARAKEET_MODEL,
    clock: Clock = time.perf_counter,
    loader: ParakeetLoader | None = None,
) -> BenchmarkResult:
    loader = loader or _load_parakeet

    load_start = clock()
    parakeet = loader(model)
    load_seconds = clock() - load_start

    transcribe_start = clock()
    result = parakeet.transcribe(str(audio_path))
    transcribe_seconds = clock() - transcribe_start
    text = str(getattr(result, "text", result)).strip()
    return BenchmarkResult(
        engine="parakeet",
        model=model,
        load_seconds=load_seconds,
        transcribe_seconds=transcribe_seconds,
        text=text,
    )


def _load_parakeet(model: str) -> Any:
    install_parakeet_librosa_shim()
    from parakeet_mlx import from_pretrained

    return from_pretrained(model)


def main() -> int:
    config = load_config()
    parser = argparse.ArgumentParser(description="Benchmark local ASR models")
    parser.add_argument(
        "--audio",
        type=Path,
        default=Path("tests/fixtures/hello_world.wav"),
        help="WAV/MP3/etc. audio file to benchmark",
    )
    parser.add_argument("--whisper-model", default=config.model)
    parser.add_argument("--parakeet-model", default=config.parakeet_model)
    parser.add_argument("--language", default=config.language)
    parser.add_argument("--skip-whisper", action="store_true")
    parser.add_argument("--skip-parakeet", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not args.audio.exists():
        parser.error(f"audio file does not exist: {args.audio}")

    results: list[BenchmarkResult] = []
    if not args.skip_whisper:
        results.append(
            benchmark_whisper(
                args.audio,
                model=args.whisper_model,
                language=args.language,
            )
        )
    if not args.skip_parakeet:
        results.append(
            benchmark_parakeet(
                args.audio,
                model=args.parakeet_model,
            )
        )

    if args.json:
        print(json.dumps([result.to_dict() for result in results], indent=2))
    else:
        for result in results:
            print(
                f"{result.engine}: model={result.model} "
                f"load={result.load_seconds:.3f}s "
                f"transcribe={result.transcribe_seconds:.3f}s "
                f"total={result.total_seconds:.3f}s"
            )
            print(f"text: {result.text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
