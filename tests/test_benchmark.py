from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest

from dictate.benchmark import benchmark_parakeet, benchmark_whisper


class FakeClock:
    def __init__(self, values: list[float]) -> None:
        self.values = values

    def __call__(self) -> float:
        return self.values.pop(0)


class FakeWhisperTranscriber:
    def __init__(self) -> None:
        self.loaded = False

    def load(self) -> None:
        self.loaded = True

    def transcribe(self, audio_path: str) -> str:
        if not self.loaded:
            raise AssertionError("transcribe called before load")
        return f"whisper:{Path(audio_path).name}"


class FakeParakeetModel:
    def transcribe(self, audio_path: str) -> object:
        return SimpleNamespace(text=f"parakeet:{Path(audio_path).name}")


class BenchmarkTests(unittest.TestCase):
    def test_benchmark_whisper_records_load_and_transcribe_times(self) -> None:
        result = benchmark_whisper(
            Path("sample.wav"),
            model="whisper-model",
            language="en",
            transcriber=FakeWhisperTranscriber(),  # type: ignore[arg-type]
            clock=FakeClock([0.0, 0.5, 0.5, 1.25]),
        )

        self.assertEqual(result.engine, "whisper")
        self.assertEqual(result.model, "whisper-model")
        self.assertAlmostEqual(result.load_seconds, 0.5)
        self.assertAlmostEqual(result.transcribe_seconds, 0.75)
        self.assertEqual(result.text, "whisper:sample.wav")

    def test_benchmark_parakeet_records_load_and_transcribe_times(self) -> None:
        loaded_models: list[str] = []

        def loader(model: str) -> FakeParakeetModel:
            loaded_models.append(model)
            return FakeParakeetModel()

        result = benchmark_parakeet(
            Path("sample.wav"),
            model="parakeet-model",
            loader=loader,
            clock=FakeClock([1.0, 1.4, 1.4, 2.0]),
        )

        self.assertEqual(loaded_models, ["parakeet-model"])
        self.assertEqual(result.engine, "parakeet")
        self.assertEqual(result.model, "parakeet-model")
        self.assertAlmostEqual(result.load_seconds, 0.4)
        self.assertAlmostEqual(result.transcribe_seconds, 0.6)
        self.assertEqual(result.text, "parakeet:sample.wav")

    def test_result_dict_rounds_times(self) -> None:
        result = benchmark_parakeet(
            Path("sample.wav"),
            model="parakeet-model",
            loader=lambda model: FakeParakeetModel(),
            clock=FakeClock([0.0, 0.12345, 0.12345, 0.98765]),
        )

        self.assertEqual(result.to_dict()["load_seconds"], 0.1235)
        self.assertEqual(result.to_dict()["transcribe_seconds"], 0.8642)


if __name__ == "__main__":
    unittest.main()
