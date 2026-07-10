from __future__ import annotations

import os
import unittest
from pathlib import Path

from dictate.config import DEFAULT_MODEL
from dictate.transcriber import ModelUnavailableError, Transcriber, configure_offline_mode

FIXTURE = Path(__file__).parent / "fixtures" / "hello_world.wav"


class OfflineModeTests(unittest.TestCase):
    def test_updates_already_imported_huggingface_state(self) -> None:
        from huggingface_hub import constants

        configure_offline_mode(offline=False)
        self.assertFalse(constants.HF_HUB_OFFLINE)

        configure_offline_mode(offline=True)

        self.assertTrue(constants.HF_HUB_OFFLINE)
        self.assertEqual(os.environ["HF_HUB_OFFLINE"], "1")


@unittest.skipUnless(
    os.environ.get("DICTATE_RUN_MLX_TESTS") == "1",
    "set DICTATE_RUN_MLX_TESTS=1 to run the MLX Whisper integration test",
)
class TranscriberIntegrationTests(unittest.TestCase):
    def test_transcribes_bundled_sample_wav(self) -> None:
        if not FIXTURE.exists():
            self.skipTest(f"missing fixture: {FIXTURE}")
        model = os.environ.get("DICTATE_TEST_MODEL", DEFAULT_MODEL)
        transcriber = Transcriber(model=model)
        try:
            text = transcriber.transcribe(str(FIXTURE)).casefold()
        except ModelUnavailableError as exc:
            self.skipTest(str(exc))
        self.assertIn("hello", text)
        self.assertIn("world", text)


if __name__ == "__main__":
    unittest.main()
