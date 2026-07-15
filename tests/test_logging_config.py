from __future__ import annotations

import logging
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from dictate import logging_config
from dictate.logging_config import configure_logging


class LoggingConfigTests(unittest.TestCase):
    def test_configure_logging_creates_rotating_log(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "logs" / "vox-terminal.log"

            configure_logging(log_file)
            logging.getLogger("test").warning("written to durable log")
            logging.shutdown()

            self.assertIn("written to durable log", log_file.read_text(encoding="utf-8"))
            self.assertTrue((log_file.parent / "crash.log").exists())
            root = logging.getLogger()
            for handler in root.handlers[:]:
                root.removeHandler(handler)
                handler.close()
            root.setLevel(logging.WARNING)

    def test_log_file_permission_failure_uses_temporary_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            requested = Path(temp_dir) / "protected" / "vox-terminal.log"
            fallback_root = Path(temp_dir) / "temporary"
            real_factory = logging_config._file_handler

            def fail_requested_path(path: Path) -> logging.Handler:
                if path == requested:
                    raise PermissionError("sandbox denied log file")
                return real_factory(path)

            with (
                mock.patch("dictate.logging_config._file_handler", side_effect=fail_requested_path),
                mock.patch("dictate.logging_config.tempfile.gettempdir", return_value=fallback_root),
            ):
                selected = configure_logging(requested)

            self.assertEqual(selected, fallback_root / "Vox Terminal" / requested.name)
            self.assertTrue(selected.exists())

            root = logging.getLogger()
            for handler in root.handlers[:]:
                root.removeHandler(handler)
                handler.close()
            root.setLevel(logging.WARNING)


if __name__ == "__main__":
    unittest.main()
