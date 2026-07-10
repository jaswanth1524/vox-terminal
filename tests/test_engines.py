from __future__ import annotations

import unittest
from types import SimpleNamespace

import numpy as np

from dictate.config import AppConfig
from dictate.engines import ParakeetEngine, build_engine
from dictate.transcriber import Transcriber


class EngineTests(unittest.TestCase):
    def test_builds_deterministic_whisper_engine(self) -> None:
        engine = build_engine(AppConfig(engine="whisper"))

        self.assertIsInstance(engine, Transcriber)
        self.assertEqual(engine.temperature, 0.0)

    def test_parakeet_warms_once_and_transcribes_arrays(self) -> None:
        backend = SimpleNamespace(preprocessor_config=SimpleNamespace(sample_rate=16_000))
        seen_sizes: list[int] = []
        engine = ParakeetEngine(
            model="local/parakeet",
            loader=lambda _model: backend,
            transcribe_impl=lambda loaded, audio, _beam_size: (
                seen_sizes.append(audio.size) or f"text:{loaded is backend}"
            ),
        )

        engine.load()
        text = engine.transcribe(np.ones(800, dtype=np.float32))

        self.assertEqual(text, "text:True")
        self.assertEqual(seen_sizes, [32_000, 64_000, 128_000, 32_000])


if __name__ == "__main__":
    unittest.main()
