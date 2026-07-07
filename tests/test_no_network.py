from __future__ import annotations

import os
import socket
import unittest
from unittest import mock

import numpy as np

from dictate.transcriber import Transcriber


class NoNetworkTests(unittest.TestCase):
    def test_transcription_path_opens_no_sockets(self) -> None:
        calls: list[str] = []

        def fake_transcribe(audio: np.ndarray, **kwargs: object) -> dict[str, str]:
            calls.append(str(kwargs["path_or_hf_repo"]))
            self.assertIsInstance(audio, np.ndarray)
            return {"text": "hello local world"}

        def blocked_socket(*args: object, **kwargs: object) -> socket.socket:
            raise AssertionError("socket opened during transcription")

        with mock.patch("socket.socket", side_effect=blocked_socket):
            transcriber = Transcriber(
                model="local-test-model",
                transcribe_impl=fake_transcribe,
            )
            text = transcriber.transcribe(np.zeros(160, dtype=np.float32))

        self.assertEqual(text, "hello local world")
        self.assertEqual(calls, ["local-test-model", "local-test-model"])
        self.assertEqual(os.environ["HF_HUB_OFFLINE"], "1")
        self.assertEqual(os.environ["TRANSFORMERS_OFFLINE"], "1")


if __name__ == "__main__":
    unittest.main()
