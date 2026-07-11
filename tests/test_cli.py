from __future__ import annotations

import sys
import unittest
from types import SimpleNamespace
from unittest import mock

from dictate.__main__ import main


class CliTests(unittest.TestCase):
    @mock.patch("dictate.__version__", "0+unknown")
    def test_self_test_rejects_missing_package_metadata(self) -> None:
        with mock.patch.object(sys, "argv", ["vox-terminal", "--self-test"]):
            result = main()

        self.assertEqual(result, 1)

    @mock.patch("dictate.logging_config.configure_logging")
    @mock.patch("dictate.__main__.load_config")
    @mock.patch("dictate.model_manager.ModelManager")
    def test_download_model_relaunches_provisioning_child(
        self,
        manager_type: mock.Mock,
        load_config: mock.Mock,
        _configure_logging: mock.Mock,
    ) -> None:
        load_config.return_value = SimpleNamespace(
            engine="parakeet",
            selected_model="example/parakeet",
            language="en",
        )
        with mock.patch.object(sys, "argv", ["vox-terminal", "--download-model"]):
            result = main()

        self.assertEqual(result, 0)
        manager_type.assert_called_once_with("parakeet", "example/parakeet", "en")
        manager_type.return_value.download.assert_called_once_with()

    @mock.patch("dictate.logging_config.configure_logging")
    @mock.patch("dictate.__main__.is_provisioning_process", return_value=False)
    def test_hidden_provisioning_command_requires_child_marker(
        self,
        _is_provisioning: mock.Mock,
        _configure_logging: mock.Mock,
    ) -> None:
        arguments = [
            "vox-terminal",
            "--provision-model",
            "--engine",
            "whisper",
            "--model",
            "example/model",
            "--language",
            "en",
        ]
        with mock.patch.object(sys, "argv", arguments):
            result = main()

        self.assertEqual(result, 2)

    @mock.patch("dictate.logging_config.configure_logging")
    @mock.patch("dictate.__main__.is_provisioning_process", return_value=True)
    @mock.patch("dictate.model_manager.provision_model")
    def test_marked_provisioning_child_downloads_then_exits(
        self,
        provision: mock.Mock,
        _is_provisioning: mock.Mock,
        _configure_logging: mock.Mock,
    ) -> None:
        arguments = [
            "vox-terminal",
            "--provision-model",
            "--engine",
            "whisper",
            "--model",
            "example/model",
            "--language",
            "en",
        ]
        with mock.patch.object(sys, "argv", arguments):
            result = main()

        self.assertEqual(result, 0)
        provision.assert_called_once_with("whisper", "example/model", "en")


if __name__ == "__main__":
    unittest.main()
