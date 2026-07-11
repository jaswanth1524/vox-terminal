#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np

from dictate.config import DEFAULT_PARAKEET_BEAM_SIZE, load_config
from dictate.engines import ParakeetEngine
from dictate.latency_benchmark import (
    BenchmarkCase,
    EngineBenchmark,
    benchmark_engine,
    meets_fast_default_gate,
    should_promote_parakeet,
)
from dictate.recorder import Recorder
from dictate.transcriber import Transcriber

PHRASES = (
    "Open the terminal and run the test suite.",
    "Create a new branch for the latency improvements.",
    "The build completed in one point five seconds.",
    "Please review pull request number forty two.",
    "Run kubectl get pods in the production namespace.",
    "Start the FastAPI development server on port eight thousand.",
    "Update the Python configuration and restart the application.",
    "Vox Terminal keeps every recording on this Mac.",
    "Copy the transcript into Visual Studio Code.",
    "The response time should remain below two seconds.",
    "Check CPU memory and network usage before deploying.",
    "Commit the changes with a concise message.",
    "Install dependencies using uv sync.",
    "The microphone permission is enabled in System Settings.",
    "Do not overwrite the current clipboard contents.",
    "Transcribe punctuation numbers and technical vocabulary.",
    "The quick brown fox jumps over the lazy dog.",
    "Schedule the benchmark for Friday at nine thirty.",
    "Accuracy and predictable latency are equally important.",
    "Finish the report and paste the final result.",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare local dictation latency and accuracy")
    parser.add_argument("--voice", default="Samantha")
    parser.add_argument("--rate", type=int, default=190)
    parser.add_argument(
        "--parakeet-beam-size",
        type=int,
        default=DEFAULT_PARAKEET_BEAM_SIZE,
    )
    parser.add_argument("--parakeet-only", action="store_true")
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="record ten prompted phrases in memory instead of synthesizing audio",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    config = load_config()

    with tempfile.TemporaryDirectory(prefix="vox-latency-") as temp_dir:
        cases = (
            _record_interactive_cases(PHRASES[:10])
            if args.interactive
            else _synthesize_cases(Path(temp_dir), voice=args.voice, rate=args.rate)
        )
        whisper = None
        if not args.parakeet_only:
            whisper = benchmark_engine(
                Transcriber(
                    model=config.model,
                    language="en",
                    initial_prompt=config.whisper_initial_prompt,
                    offline=True,
                    temperature=0.0,
                ),
                cases,
            )
        parakeet = benchmark_engine(
            ParakeetEngine(
                model=config.parakeet_model,
                offline=True,
                beam_size=args.parakeet_beam_size,
                quantization_bits=config.parakeet_quantization_bits or None,
            ),
            cases,
        )

    fast_default = whisper is not None and meets_fast_default_gate(whisper, parakeet)
    accuracy_parity = whisper is not None and should_promote_parakeet(whisper, parakeet)
    payload = {"parakeet": _result_dict(parakeet)}
    if whisper is not None:
        payload["whisper"] = _result_dict(whisper)
        payload["fast_default_gate"] = fast_default
        payload["whisper_accuracy_parity"] = accuracy_parity
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        for name in ("whisper", "parakeet"):
            if name not in payload:
                continue
            result = payload[name]
            print(
                f"{name}: p50={result['p50_ms']:.0f}ms p95={result['p95_ms']:.0f}ms "
                f"WER={result['word_error_rate']:.1%}"
            )
        if whisper is not None:
            print(f"fast default gate: {'PASS' if fast_default else 'FAIL'}")
            print(f"Whisper accuracy parity: {'PASS' if accuracy_parity else 'FAIL'}")
    if whisper is None:
        return 0
    return 0 if accuracy_parity else 1


def _synthesize_cases(directory: Path, *, voice: str, rate: int) -> list[BenchmarkCase]:
    cases = []
    for index, phrase in enumerate(PHRASES):
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
        raise ValueError(f"Unexpected benchmark audio format: {channels=} {width=} {rate=}")
    return np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32_768.0


def _record_interactive_cases(phrases: tuple[str, ...]) -> list[BenchmarkCase]:
    recorder = Recorder(max_seconds=30)
    cases = []
    print("Interactive audio stays in memory and is discarded after this benchmark.")
    for index, phrase in enumerate(phrases, start=1):
        print(f"\n{index}/{len(phrases)} Read: {phrase}")
        input("Press Return to start recording...")
        recorder.start()
        input("Speak, then press Return to stop...")
        recording = recorder.stop()
        cases.append(BenchmarkCase(phrase, recording.audio))
    return cases


def _result_dict(result: EngineBenchmark) -> dict[str, object]:
    return {
        "p50_ms": result.p50_ms,
        "p95_ms": result.p95_ms,
        "word_error_rate": result.word_error_rate,
        "samples_ms": list(result.samples_ms),
        "hypotheses": list(result.hypotheses),
    }


if __name__ == "__main__":
    raise SystemExit(main())
