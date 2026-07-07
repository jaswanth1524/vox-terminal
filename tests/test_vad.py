from __future__ import annotations

import unittest

import numpy as np

from dictate.vad import SileroVadAutoStop


class VadTests(unittest.TestCase):
    def test_stops_after_speech_then_trailing_silence(self) -> None:
        def timestamps(audio: np.ndarray, *args: object, **kwargs: object) -> list[dict[str, float]]:
            del audio, args, kwargs
            return [{"start": 0.1, "end": 0.5}]

        vad = SileroVadAutoStop(
            silence_seconds=0.5,
            min_speech_seconds=0.2,
            get_speech_timestamps=timestamps,
            model=object(),
        )

        decision = vad.decide(np.ones(16_000, dtype=np.float32), sample_rate=16_000)

        self.assertTrue(decision.has_speech)
        self.assertTrue(decision.should_stop)
        self.assertAlmostEqual(decision.trailing_silence_seconds, 0.5)

    def test_keeps_recording_before_enough_silence(self) -> None:
        def timestamps(audio: np.ndarray, *args: object, **kwargs: object) -> list[dict[str, float]]:
            del audio, args, kwargs
            return [{"start": 0.1, "end": 0.9}]

        vad = SileroVadAutoStop(
            silence_seconds=0.5,
            min_speech_seconds=0.2,
            get_speech_timestamps=timestamps,
            model=object(),
        )

        decision = vad.decide(np.ones(16_000, dtype=np.float32), sample_rate=16_000)

        self.assertTrue(decision.has_speech)
        self.assertFalse(decision.should_stop)

    def test_ignores_audio_without_minimum_speech(self) -> None:
        def timestamps(audio: np.ndarray, *args: object, **kwargs: object) -> list[dict[str, float]]:
            del audio, args, kwargs
            return [{"start": 0.1, "end": 0.15}]

        vad = SileroVadAutoStop(
            silence_seconds=0.5,
            min_speech_seconds=0.2,
            get_speech_timestamps=timestamps,
            model=object(),
        )

        decision = vad.decide(np.ones(16_000, dtype=np.float32), sample_rate=16_000)

        self.assertFalse(decision.has_speech)
        self.assertFalse(decision.should_stop)


if __name__ == "__main__":
    unittest.main()
