from __future__ import annotations

import os
import unittest
from unittest import mock

from dictate.model_manager import ModelManager, ModelState


class ModelManagerTests(unittest.TestCase):
    @mock.patch("huggingface_hub.snapshot_download")
    def test_cached_check_never_allows_network(self, snapshot_download: mock.Mock) -> None:
        states: list[ModelState] = []

        self.assertTrue(ModelManager("example/model", "en", states.append).is_available())

        snapshot_download.assert_called_once_with(
            repo_id="example/model",
            local_files_only=True,
        )
        self.assertEqual(states, [ModelState.CHECKING, ModelState.READY])

    @mock.patch("dictate.model_manager.Transcriber")
    @mock.patch("huggingface_hub.snapshot_download")
    def test_download_returns_process_to_offline_mode(
        self,
        snapshot_download: mock.Mock,
        transcriber: mock.Mock,
    ) -> None:
        states: list[ModelState] = []

        ModelManager("example/model", "en", states.append).download()

        snapshot_download.assert_called_once_with(
            repo_id="example/model",
            local_files_only=False,
        )
        transcriber.return_value.load.assert_called_once_with()
        self.assertEqual(os.environ["HF_HUB_OFFLINE"], "1")
        self.assertEqual(states[-1], ModelState.READY)


if __name__ == "__main__":
    unittest.main()
