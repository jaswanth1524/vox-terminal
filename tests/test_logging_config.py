from __future__ import annotations

import logging
import tempfile
import unittest
from pathlib import Path

from dictate.logging_config import configure_logging


class LoggingConfigTests(unittest.TestCase):
    def test_configure_logging_creates_rotating_log(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "logs" / "vox-terminal.log"

            configure_logging(log_file)
            logging.getLogger("test").warning("written to durable log")
            logging.shutdown()

            self.assertIn("written to durable log", log_file.read_text(encoding="utf-8"))
            root = logging.getLogger()
            for handler in root.handlers[:]:
                root.removeHandler(handler)
                handler.close()
            root.setLevel(logging.WARNING)


if __name__ == "__main__":
    unittest.main()
