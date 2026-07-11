from __future__ import annotations

import unittest

import numpy as np

from dictate.vad import SileroVadAutoStop, StreamingEnergyVad

SAMPLE_RATE = 16_000


def samples(seconds: float, amplitude: float) -> np.ndarray:
    return np.full(round(seconds * SAMPLE_RATE), amplitude, dtype=np.float32)


class VadTests(unittest.TestCase):
    def make_vad(self, **overrides: float) -> StreamingEnergyVad:
        settings = {
            "silence_seconds": 0.5,
            "min_speech_seconds": 0.25,
            "speech_rms_threshold": 0.002,
            "frame_seconds": 0.02,
            "calibration_seconds": 0.1,
        }
        settings.update(overrides)
        return StreamingEnergyVad(**settings)

    def test_silence_never_counts_as_speech(self) -> None:
        vad = self.make_vad()

        decision = vad.process(samples(1.0, 0.0), sample_rate=SAMPLE_RATE)

        self.assertFalse(decision.has_speech)
        self.assertFalse(decision.should_stop)
        self.assertEqual(decision.trailing_silence_seconds, 0.0)

    def test_adaptive_noise_floor_ignores_steady_background_noise(self) -> None:
        vad = self.make_vad()
        vad.process(samples(0.1, 0.001), sample_rate=SAMPLE_RATE)
        calibrated = vad.state()

        decision = vad.process(samples(0.5, 0.0025), sample_rate=SAMPLE_RATE)

        self.assertAlmostEqual(calibrated.noise_floor, 0.001, places=6)
        self.assertAlmostEqual(calibrated.speech_threshold, 0.003, places=6)
        self.assertFalse(decision.has_speech)
        self.assertGreater(vad.state().speech_threshold, calibrated.speech_threshold)

    def test_calibration_does_not_absorb_soft_speech(self) -> None:
        vad = self.make_vad()

        decision = vad.process(samples(0.5, 0.004), sample_rate=SAMPLE_RATE)

        self.assertTrue(decision.has_speech)
        self.assertEqual(vad.state().noise_floor, 0.0)

    def test_speech_is_accumulated_across_new_chunks(self) -> None:
        vad = self.make_vad()
        vad.process(samples(0.1, 0.001), sample_rate=SAMPLE_RATE)
        noise_floor = vad.state().noise_floor

        for chunk in np.array_split(samples(0.3, 0.02), 7):
            decision = vad.process(chunk, sample_rate=SAMPLE_RATE)

        self.assertTrue(decision.has_speech)
        self.assertFalse(decision.should_stop)
        self.assertAlmostEqual(vad.state().voiced_seconds, 0.3)
        self.assertAlmostEqual(vad.state().noise_floor, noise_floor)

    def test_speech_at_the_start_is_not_learned_as_noise(self) -> None:
        vad = self.make_vad()

        decision = vad.process(samples(0.3, 0.02), sample_rate=SAMPLE_RATE)

        self.assertTrue(decision.has_speech)
        self.assertAlmostEqual(vad.state().voiced_seconds, 0.3)
        self.assertEqual(vad.state().noise_floor, 0.0)

    def test_stops_after_speech_then_trailing_silence(self) -> None:
        vad = self.make_vad()
        vad.process(samples(0.1, 0.0), sample_rate=SAMPLE_RATE)
        speech_decision = vad.process(samples(0.3, 0.02), sample_rate=SAMPLE_RATE)
        early_decision = vad.process(samples(0.48, 0.0), sample_rate=SAMPLE_RATE)
        stop_decision = vad.process(samples(0.02, 0.0), sample_rate=SAMPLE_RATE)

        self.assertTrue(speech_decision.has_speech)
        self.assertEqual(speech_decision.trailing_silence_seconds, 0.0)
        self.assertFalse(early_decision.should_stop)
        self.assertAlmostEqual(early_decision.trailing_silence_seconds, 0.48)
        self.assertTrue(stop_decision.should_stop)
        self.assertAlmostEqual(stop_decision.trailing_silence_seconds, 0.5)

    def test_ignores_audio_without_minimum_speech(self) -> None:
        vad = self.make_vad()
        vad.process(samples(0.1, 0.0), sample_rate=SAMPLE_RATE)
        vad.process(samples(0.2, 0.02), sample_rate=SAMPLE_RATE)

        decision = vad.process(samples(0.8, 0.0), sample_rate=SAMPLE_RATE)

        self.assertFalse(decision.has_speech)
        self.assertFalse(decision.should_stop)
        self.assertEqual(decision.trailing_silence_seconds, 0.0)

    def test_reset_clears_state_and_allows_a_new_sample_rate(self) -> None:
        vad = self.make_vad()
        vad.process(samples(0.5, 0.02), sample_rate=SAMPLE_RATE)

        vad.reset()

        state = vad.state()
        self.assertEqual(state.processed_seconds, 0.0)
        self.assertEqual(state.voiced_seconds, 0.0)
        self.assertEqual(state.noise_floor, 0.0)
        self.assertEqual(state.pending_samples, 0)
        self.assertEqual(state.decision, vad.decision())
        vad.process(np.zeros(800, dtype=np.float32), sample_rate=8_000)

    def test_retained_audio_state_is_bounded_to_one_analysis_frame(self) -> None:
        vad = self.make_vad(calibration_seconds=0.0)
        chunk = np.zeros(337, dtype=np.float32)
        total_samples = 0

        for _ in range(500):
            vad.process(chunk, sample_rate=SAMPLE_RATE)
            total_samples += chunk.size

        state = vad.state()
        processed_samples = round(state.processed_seconds * SAMPLE_RATE)
        self.assertLess(state.pending_samples, round(vad.frame_seconds * SAMPLE_RATE))
        self.assertEqual(processed_samples + state.pending_samples, total_samples)

    def test_sample_rate_change_requires_reset(self) -> None:
        vad = self.make_vad()
        vad.process(np.zeros(320, dtype=np.float32), sample_rate=SAMPLE_RATE)

        with self.assertRaisesRegex(ValueError, "reset"):
            vad.process(np.zeros(160, dtype=np.float32), sample_rate=8_000)

    def test_original_class_name_remains_compatible(self) -> None:
        self.assertIs(SileroVadAutoStop, StreamingEnergyVad)


if __name__ == "__main__":
    unittest.main()
