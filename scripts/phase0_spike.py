#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dictate.config import load_config
from dictate.postprocess import clean_transcript
from dictate.recorder import Recorder
from dictate.transcriber import ModelUnavailableError, Transcriber


def main() -> int:
    config = load_config()
    transcriber = Transcriber(
        model=config.model,
        language=config.language,
        initial_prompt=config.initial_prompt,
        offline=True,
    )
    try:
        print(f"Loading model: {config.model}", flush=True)
        transcriber.load()
    except ModelUnavailableError as exc:
        print(exc, file=sys.stderr)
        return 1

    recorder = Recorder(max_seconds=5)
    print("Recording for 5 seconds...", flush=True)
    recorder.start()
    time.sleep(5)
    recording = recorder.stop()
    print("Transcribing...", flush=True)
    transcript = transcriber.transcribe(recording.audio)
    print(clean_transcript(transcript, rms=recording.rms), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
