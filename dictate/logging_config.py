from __future__ import annotations

import logging
import tempfile
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .paths import DEFAULT_PATHS

LOG_FORMAT = "%(asctime)s %(levelname)s %(threadName)s %(message)s"


def configure_logging(
    log_file: Path = DEFAULT_PATHS.log_file,
    *,
    foreground: bool = False,
) -> Path:
    """Configure durable app logging and optional terminal output."""

    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        log_file = Path(tempfile.gettempdir()) / "Vox Terminal" / log_file.name
        log_file.parent.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [
        RotatingFileHandler(
            log_file,
            maxBytes=2 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
    ]
    if foreground:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=handlers,
        force=True,
    )
    return log_file
