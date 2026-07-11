from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest import mock

import numpy as np

from dictate.config import AppConfig
from dictate.engines import ParakeetEngine, build_engine
from dictate.transcriber import Transcriber


class EngineTests(unittest.TestCase):
    def test_builds_deterministic_whisper_engine(self) -> None:
        with mock.patch("dictate.model_manager.resolve_cached_model", return_value=None):
            engine = build_engine(AppConfig(engine="whisper"))

        self.assertIsInstance(engine, Transcriber)
        self.assertEqual(engine.temperature, 0.0)

    def test_build_engine_uses_resolved_local_snapshot(self) -> None:
        with mock.patch(
            "dictate.model_manager.resolve_cached_model",
            return_value="/cache/parakeet/snapshot",
        ):
            engine = build_engine(AppConfig(engine="parakeet"))

        self.assertEqual(engine.model, "/cache/parakeet/snapshot")
        self.assertEqual(engine.quantization_bits, 3)

    def test_parakeet_quantizes_before_warmup(self) -> None:
        backend = SimpleNamespace(preprocessor_config=SimpleNamespace(sample_rate=16_000))
        events: list[str] = []
        engine = ParakeetEngine(
            model="local/parakeet",
            quantization_bits=4,
            loader=lambda _model: backend,
            quantize_impl=lambda loaded, bits: events.append(
                f"quantize:{loaded is backend}:{bits}"
            ),
            transcribe_impl=lambda _loaded, _audio, _beam_size: events.append("warm") or "",
        )

        engine.load()

        self.assertEqual(events, ["quantize:True:4", "warm", "warm", "warm"])

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

    def test_parakeet_releases_backend_and_can_reload(self) -> None:
        backend = SimpleNamespace(preprocessor_config=SimpleNamespace(sample_rate=16_000))
        loads: list[str] = []
        engine = ParakeetEngine(
            model="local/parakeet",
            loader=lambda model: loads.append(model) or backend,
            transcribe_impl=lambda _loaded, _audio, _beam_size: "text",
        )
        engine.load()

        engine.close()
        engine.load()

        self.assertEqual(loads, ["local/parakeet", "local/parakeet"])


if __name__ == "__main__":
    unittest.main()
