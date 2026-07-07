from __future__ import annotations

import time
import unittest

import numpy as np

from dictate.__main__ import DictateService
from dictate.config import AppConfig
from dictate.history import TranscriptHistory
from dictate.recorder import Recording


class FakeRecorder:
    def __init__(self, duration: float = 0.1) -> None:
        self.duration = duration
        self.is_recording = False
        self.starts = 0
        self.stops = 0

    def start(self) -> None:
        self.starts += 1
        self.is_recording = True

    def stop(self) -> Recording:
        self.stops += 1
        self.is_recording = False
        now = time.monotonic()
        return Recording(
            audio=np.zeros(160, dtype=np.float32),
            sample_rate=16_000,
            started_at=now - self.duration,
            stopped_at=now,
        )


class FakeTranscriber:
    def __init__(self) -> None:
        self.loads = 0
        self.calls = 0

    def load(self) -> None:
        self.loads += 1

    def transcribe(self, audio: np.ndarray) -> str:
        del audio
        self.calls += 1
        return "hello"


class FakeInjector:
    def __init__(self) -> None:
        self.injected: list[str] = []

    def inject(self, text: str) -> None:
        self.injected.append(text)


class ServiceTests(unittest.TestCase):
    def test_toggle_press_starts_then_stops(self) -> None:
        recorder = FakeRecorder(duration=0.1)
        service = DictateService(
            AppConfig(mode="toggle", sounds=False, min_recording_ms=300),
            recorder=recorder,  # type: ignore[arg-type]
            transcriber=FakeTranscriber(),  # type: ignore[arg-type]
            injector=FakeInjector(),
        )

        service._on_hotkey_press()
        service._on_hotkey_press()

        self.assertEqual(recorder.starts, 1)
        self.assertEqual(recorder.stops, 1)
        self.assertEqual(service.status, "idle")

    def test_hold_release_ignores_short_recording(self) -> None:
        recorder = FakeRecorder(duration=0.1)
        transcriber = FakeTranscriber()
        service = DictateService(
            AppConfig(mode="hold", sounds=False, min_recording_ms=300),
            recorder=recorder,  # type: ignore[arg-type]
            transcriber=transcriber,  # type: ignore[arg-type]
            injector=FakeInjector(),
        )

        service._on_hotkey_press()
        service._on_hotkey_release()

        self.assertEqual(recorder.starts, 1)
        self.assertEqual(recorder.stops, 1)
        self.assertEqual(transcriber.calls, 0)
        self.assertEqual(service.status, "idle")

    def test_ignores_press_while_transcribing(self) -> None:
        recorder = FakeRecorder()
        service = DictateService(
            AppConfig(sounds=False),
            recorder=recorder,  # type: ignore[arg-type]
            transcriber=FakeTranscriber(),  # type: ignore[arg-type]
            injector=FakeInjector(),
        )
        service._transcribing.acquire()
        try:
            service._on_hotkey_press()
        finally:
            service._transcribing.release()

        self.assertEqual(recorder.starts, 0)

    def test_max_recording_time_stops_active_recording(self) -> None:
        recorder = FakeRecorder(duration=0.4)
        service = DictateService(
            AppConfig(sounds=False, min_recording_ms=1_000),
            recorder=recorder,  # type: ignore[arg-type]
            transcriber=FakeTranscriber(),  # type: ignore[arg-type]
            injector=FakeInjector(),
        )

        service._on_hotkey_press()
        service._on_max_recording_time()

        self.assertEqual(recorder.stops, 1)

    def test_successful_transcript_is_added_to_history(self) -> None:
        history = TranscriptHistory(max_size=5)
        injector = FakeInjector()
        service = DictateService(
            AppConfig(sounds=False),
            transcriber=FakeTranscriber(),  # type: ignore[arg-type]
            injector=injector,
            history=history,
        )
        now = time.monotonic()
        recording = Recording(
            audio=np.ones(160, dtype=np.float32),
            sample_rate=16_000,
            started_at=now - 1,
            stopped_at=now,
        )

        service._transcribe_and_inject(recording)

        self.assertEqual(injector.injected, ["hello"])
        self.assertEqual([entry.text for entry in history.entries()], ["hello"])


if __name__ == "__main__":
    unittest.main()
