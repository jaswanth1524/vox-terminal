from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path
from unittest import mock

import numpy as np

from dictate.config import DEFAULT_MODEL
from dictate.transcriber import (
    ModelUnavailableError,
    Transcriber,
    configure_offline_mode,
    download_model,
)


class OfflineModeTests(unittest.TestCase):
    def test_updates_already_imported_huggingface_state(self) -> None:
        from huggingface_hub import constants

        configure_offline_mode(offline=False)
        self.assertFalse(constants.HF_HUB_OFFLINE)

        configure_offline_mode(offline=True)

        self.assertTrue(constants.HF_HUB_OFFLINE)
        self.assertEqual(os.environ["HF_HUB_OFFLINE"], "1")

    def test_whisper_uses_single_greedy_temperature_and_realistic_warmup(self) -> None:
        calls: list[tuple[int, float]] = []

        def transcribe(audio: object, **kwargs: object) -> dict[str, str]:
            calls.append((audio.size, kwargs["temperature"]))
            return {"text": "ready"}

        engine = Transcriber(model="cached/model", transcribe_impl=transcribe)
        engine.load()

        self.assertEqual(calls, [(16_000, 0.0)])

    def test_close_allows_injected_transcriber_to_warm_again(self) -> None:
        calls: list[int] = []

        def transcribe(audio: object, **_kwargs: object) -> dict[str, str]:
            calls.append(audio.size)
            return {"text": "ready"}

        engine = Transcriber(model="cached/model", transcribe_impl=transcribe)
        engine.load()

        engine.close()
        engine.load()

        self.assertEqual(calls, [16_000, 16_000])

    @mock.patch("dictate.model_manager.resolve_cached_model", return_value=None)
    def test_missing_model_error_points_to_explicit_provisioning(
        self,
        _resolve_cached_model: mock.Mock,
    ) -> None:
        engine = Transcriber(
            model="missing/model",
            transcribe_impl=mock.Mock(side_effect=RuntimeError("not cached")),
        )

        with self.assertRaisesRegex(ModelUnavailableError, "--download-model"):
            engine.load()

    @mock.patch("dictate.model_manager.resolve_cached_model", return_value=Path("/cache/model"))
    def test_cached_model_warmup_error_is_not_misclassified(
        self,
        _resolve_cached_model: mock.Mock,
    ) -> None:
        engine = Transcriber(
            model="cached/model",
            transcribe_impl=mock.Mock(side_effect=RuntimeError("invalid weights")),
        )

        with self.assertRaisesRegex(RuntimeError, "invalid weights"):
            engine.load()

    @mock.patch("dictate.model_manager.ModelManager")
    def test_legacy_download_helper_uses_provisioning_child(
        self,
        manager_type: mock.Mock,
    ) -> None:
        download_model("example/whisper", "en")

        manager_type.assert_called_once_with("whisper", "example/whisper", "en")
        manager_type.return_value.download.assert_called_once_with()


@unittest.skipUnless(
    os.environ.get("DICTATE_RUN_MLX_TESTS") == "1",
    "set DICTATE_RUN_MLX_TESTS=1 to run the MLX Whisper integration test",
)
class TranscriberIntegrationTests(unittest.TestCase):
    def test_transcribes_synthesized_speech_array(self) -> None:
        with tempfile.TemporaryDirectory(prefix="vox-whisper-test-") as temp_dir:
            speech_path = Path(temp_dir) / "hello-world.wav"
            subprocess.run(
                [
                    "say",
                    "-v",
                    "Samantha",
                    "-o",
                    str(speech_path),
                    "--file-format=WAVE",
                    "--data-format=LEI16@16000",
                    "Hello world.",
                ],
                check=True,
                capture_output=True,
            )
            with wave.open(str(speech_path), "rb") as audio_file:
                self.assertEqual(audio_file.getnchannels(), 1)
                self.assertEqual(audio_file.getsampwidth(), 2)
                self.assertEqual(audio_file.getframerate(), 16_000)
                frames = audio_file.readframes(audio_file.getnframes())
        audio = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32_768.0
        model = os.environ.get("DICTATE_TEST_MODEL", DEFAULT_MODEL)
        transcriber = Transcriber(model=model)
        try:
            text = transcriber.transcribe(audio).casefold()
        except ModelUnavailableError as exc:
            self.skipTest(str(exc))
        self.assertIn("hello", text)
        self.assertIn("world", text)


if __name__ == "__main__":
    unittest.main()
