from __future__ import annotations

import os
from pathlib import Path
import unittest

from dictate.config import DEFAULT_MODEL
from dictate.transcriber import ModelUnavailableError, Transcriber


FIXTURE = Path(__file__).parent / "fixtures" / "hello_world.wav"


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
