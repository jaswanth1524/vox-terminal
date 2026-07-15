from __future__ import annotations

import faulthandler
import logging
import sys
import tempfile
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TextIO

from .paths import DEFAULT_PATHS

LOG_FORMAT = "%(asctime)s %(levelname)s %(threadName)s %(message)s"
MAX_CRASH_LOG_BYTES = 2 * 1024 * 1024

_fault_log: TextIO | None = None


def configure_logging(
    log_file: Path = DEFAULT_PATHS.log_file,
    *,
    foreground: bool = False,
) -> Path:
    """Configure durable app logging and optional terminal output."""

    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = _file_handler(log_file)
    except OSError as exc:
        failed_log_file = log_file
        log_file = Path(tempfile.gettempdir()) / "Vox Terminal" / log_file.name
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = _file_handler(log_file)
        # basicConfig is not active yet, so record the fallback after handlers
        # are installed below.
        fallback_warning = (
            f"Could not open {failed_log_file}; using temporary log {log_file}: {exc}"
        )
    else:
        fallback_warning = None
    handlers: list[logging.Handler] = [
        file_handler,
    ]
    if foreground:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=handlers,
        force=True,
    )
    if fallback_warning is not None:
        logging.warning(fallback_warning)
    _configure_crash_reporting(log_file.parent / "crash.log")
    return log_file


def _file_handler(log_file: Path) -> RotatingFileHandler:
    return RotatingFileHandler(
        log_file,
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )


def _configure_crash_reporting(crash_file: Path) -> None:
    """Persist failures that ordinary Python logging cannot observe."""

    global _fault_log
    try:
        if _fault_log is not None:
            if faulthandler.is_enabled():
                faulthandler.disable()
            _fault_log.close()
        if crash_file.exists() and crash_file.stat().st_size >= MAX_CRASH_LOG_BYTES:
            crash_file.replace(crash_file.with_suffix(".previous.log"))
        _fault_log = crash_file.open("a", encoding="utf-8")
        faulthandler.enable(file=_fault_log, all_threads=True)
    except OSError as exc:
        _fault_log = None
        logging.warning("Could not enable native crash reporting: %s", exc)

    sys.excepthook = _log_uncaught_exception
    threading.excepthook = _log_uncaught_thread_exception


def _log_uncaught_exception(
    exception_type: type[BaseException],
    exception: BaseException,
    traceback: object,
) -> None:
    logging.critical(
        "Unhandled main-thread exception",
        exc_info=(exception_type, exception, traceback),
    )


def _log_uncaught_thread_exception(args: threading.ExceptHookArgs) -> None:
    logging.critical(
        "Unhandled exception in thread %s",
        args.thread.name if args.thread is not None else "unknown",
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
    )
