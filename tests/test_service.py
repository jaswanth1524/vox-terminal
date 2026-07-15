from __future__ import annotations

import time
import unittest
from types import SimpleNamespace

import numpy as np

from dictate.__main__ import DictateService
from dictate.config import AppConfig
from dictate.history import TranscriptHistory
from dictate.recorder import Recording


class FakeRecorder:
    def __init__(self, duration: float = 0.1) -> None:
        self.duration = duration
        self.sample_rate = 16_000
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

    def snapshot(self) -> Recording:
        now = time.monotonic()
        return Recording(
            audio=np.ones(16_000, dtype=np.float32),
            sample_rate=16_000,
            started_at=now - 1,
            stopped_at=now,
        )

    def read_new_audio(self) -> np.ndarray:
        return np.ones(16_000, dtype=np.float32)


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

    def close(self) -> None:
        pass


class FakeInjector:
    def __init__(self) -> None:
        self.injected: list[str] = []

    def inject(self, text: str) -> None:
        self.injected.append(text)


class FakeVadAutoStop:
    def __init__(self, should_stop: bool = True) -> None:
        self.should_stop = should_stop
        self.calls = 0

    def reset(self) -> None:
        pass

    def process(self, audio: np.ndarray, *, sample_rate: int) -> object:
        del audio, sample_rate
        self.calls += 1
        return SimpleNamespace(
            should_stop=self.should_stop,
            trailing_silence_seconds=1.0,
        )


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
        self.assertEqual(len(service.latency_history.samples()), 1)

        service.clear_performance_data()

        self.assertEqual(service.latency_history.samples(), ())

    def test_vad_auto_stop_stops_toggle_recording(self) -> None:
        recorder = FakeRecorder(duration=2.0)
        fake_vad = FakeVadAutoStop()
        service = DictateService(
            AppConfig(
                mode="toggle",
                sounds=False,
                min_recording_ms=1_000,
                vad_poll_seconds=0.01,
            ),
            recorder=recorder,  # type: ignore[arg-type]
            transcriber=FakeTranscriber(),  # type: ignore[arg-type]
            injector=FakeInjector(),
            vad_auto_stop=fake_vad,  # type: ignore[arg-type]
        )

        service._on_hotkey_press()
        deadline = time.monotonic() + 1
        while recorder.stops == 0 and time.monotonic() < deadline:
            time.sleep(0.01)
        service._stop_vad_monitor()

        self.assertEqual(recorder.stops, 1)
        self.assertGreaterEqual(fake_vad.calls, 1)

    def test_status_callback_failure_does_not_escape_worker_boundary(self) -> None:
        service = DictateService(
            AppConfig(sounds=False),
            transcriber=FakeTranscriber(),  # type: ignore[arg-type]
            injector=FakeInjector(),
        )
        service._status_callback = lambda _status: (_ for _ in ()).throw(
            RuntimeError("render failed")
        )

        with self.assertLogs(level="ERROR") as captured:
            service._set_status("recording")

        self.assertEqual(service.status, "recording")
        self.assertIn("render failed", "\n".join(captured.output))

    def test_stop_contains_native_cleanup_failures(self) -> None:
        class FailingRecorder(FakeRecorder):
            def stop(self) -> Recording:
                self.is_recording = False
                raise RuntimeError("audio device vanished")

        class FailingTranscriber(FakeTranscriber):
            def close(self) -> None:
                raise RuntimeError("model close failed")

        recorder = FailingRecorder()
        recorder.is_recording = True
        service = DictateService(
            AppConfig(sounds=False),
            recorder=recorder,  # type: ignore[arg-type]
            transcriber=FailingTranscriber(),  # type: ignore[arg-type]
            injector=FakeInjector(),
        )

        with self.assertLogs(level="WARNING") as captured:
            service.stop()

        self.assertEqual(service.status, "stopped")
        messages = "\n".join(captured.output)
        self.assertIn("audio device vanished", messages)
        self.assertIn("model close failed", messages)


if __name__ == "__main__":
    unittest.main()
