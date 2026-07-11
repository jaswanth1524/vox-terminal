from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from dictate.model_manager import (
    ModelManager,
    ModelProvisioningError,
    ModelState,
    provision_model,
    provisioning_command,
    resolve_cached_model,
)
from dictate.network import PROVISIONING_ENV


class ModelManagerTests(unittest.TestCase):
    @mock.patch("huggingface_hub.snapshot_download", return_value="/cache/snapshot")
    def test_cached_check_never_allows_network(self, snapshot_download: mock.Mock) -> None:
        states: list[ModelState] = []

        self.assertTrue(
            ModelManager("whisper", "example/model", "en", states.append).is_available()
        )

        snapshot_download.assert_called_once_with(
            repo_id="example/model",
            local_files_only=True,
        )
        self.assertEqual(states, [ModelState.CHECKING, ModelState.READY])

    @mock.patch("huggingface_hub.snapshot_download", side_effect=OSError("not cached"))
    def test_cached_model_resolver_returns_none_when_missing(
        self,
        snapshot_download: mock.Mock,
    ) -> None:
        self.assertIsNone(resolve_cached_model("example/missing"))
        snapshot_download.assert_called_once_with(
            repo_id="example/missing",
            local_files_only=True,
        )

    @mock.patch("dictate.model_manager.resolve_cached_model")
    @mock.patch("dictate.model_manager.subprocess.run")
    def test_download_uses_marked_child_and_rechecks_local_cache(
        self,
        run: mock.Mock,
        resolve: mock.Mock,
    ) -> None:
        resolve.return_value = Path("/cache/snapshot")
        states: list[ModelState] = []

        snapshot = ModelManager(
            "parakeet",
            "example/parakeet",
            "en",
            states.append,
        ).download()

        self.assertEqual(snapshot, Path("/cache/snapshot"))
        command = run.call_args.args[0]
        self.assertEqual(command[:3], [sys.executable, "-m", "dictate"])
        self.assertIn("--provision-model", command)
        self.assertIn("example/parakeet", command)
        self.assertTrue(run.call_args.kwargs["check"])
        environment = run.call_args.kwargs["env"]
        self.assertEqual(environment[PROVISIONING_ENV], "1")
        self.assertNotIn("HF_HUB_OFFLINE", environment)
        resolve.assert_called_once_with("example/parakeet")
        self.assertEqual(states, [ModelState.DOWNLOADING, ModelState.READY])

    @mock.patch("dictate.model_manager.resolve_cached_model", return_value=None)
    @mock.patch("dictate.model_manager.subprocess.run")
    def test_download_fails_when_child_did_not_create_cache(
        self,
        run: mock.Mock,
        _resolve: mock.Mock,
    ) -> None:
        states: list[ModelState] = []

        with self.assertRaisesRegex(ModelProvisioningError, "not available"):
            ModelManager("whisper", "example/model", "en", states.append).download()

        run.assert_called_once()
        self.assertEqual(states, [ModelState.DOWNLOADING, ModelState.ERROR])

    @mock.patch("dictate.model_manager.resolve_cached_model")
    @mock.patch(
        "dictate.model_manager.subprocess.run",
        side_effect=subprocess.CalledProcessError(1, ["provision"]),
    )
    def test_download_surfaces_child_failure(
        self,
        _run: mock.Mock,
        resolve: mock.Mock,
    ) -> None:
        states: list[ModelState] = []

        with self.assertRaisesRegex(ModelProvisioningError, "process failed"):
            ModelManager("whisper", "example/model", "en", states.append).download()

        resolve.assert_not_called()
        self.assertEqual(states, [ModelState.DOWNLOADING, ModelState.ERROR])

    def test_frozen_app_relaunches_its_own_executable(self) -> None:
        with mock.patch.object(sys, "frozen", True, create=True):
            command = provisioning_command("whisper", "example/model", "en")

        self.assertEqual(command[0], sys.executable)
        self.assertEqual(command[1], "--provision-model")
        self.assertNotIn("-m", command)

    @mock.patch("dictate.model_manager.is_provisioning_process", return_value=False)
    def test_direct_in_process_provisioning_is_refused(self, _authorized: mock.Mock) -> None:
        with self.assertRaisesRegex(ModelProvisioningError, "Refusing"):
            provision_model("whisper", "example/model", "en")

    @mock.patch("dictate.model_manager.is_provisioning_process", return_value=True)
    @mock.patch("huggingface_hub.snapshot_download", return_value="/cache/downloaded")
    def test_authorized_child_downloads_without_warming_engine(
        self,
        snapshot_download: mock.Mock,
        _authorized: mock.Mock,
    ) -> None:
        path = provision_model("parakeet", "example/parakeet", "en")

        self.assertEqual(path, Path("/cache/downloaded"))
        snapshot_download.assert_called_once_with(
            repo_id="example/parakeet",
            local_files_only=False,
        )

    def tearDown(self) -> None:
        os.environ.pop(PROVISIONING_ENV, None)


if __name__ == "__main__":
    unittest.main()
