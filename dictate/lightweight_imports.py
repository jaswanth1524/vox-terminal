from __future__ import annotations

import sys
from collections.abc import Callable
from types import ModuleType
from typing import Any


def install_whisper_timing_shims() -> None:
    """Install APIs imported only by mlx-whisper's disabled word timing path.

    Vox Terminal never requests word timestamps, but mlx-whisper imports Numba
    and SciPy for that optional path at module import time. Small placeholders
    keep the regular transcription path available without loading or packaging
    those heavyweight dependencies.
    """

    numba = ModuleType("numba")
    numba.jit = _identity_jit  # type: ignore[attr-defined]

    signal = ModuleType("scipy.signal")
    signal.medfilt = _word_timing_unavailable  # type: ignore[attr-defined]
    scipy = ModuleType("scipy")
    scipy.signal = signal  # type: ignore[attr-defined]

    sys.modules["numba"] = numba
    sys.modules["scipy"] = scipy
    sys.modules["scipy.signal"] = signal


def _identity_jit(*args: Any, **_kwargs: Any) -> Any:
    if args and callable(args[0]):
        return args[0]

    def decorate(function: Callable[..., Any]) -> Callable[..., Any]:
        return function

    return decorate


def _word_timing_unavailable(*_args: Any, **_kwargs: Any) -> None:
    raise RuntimeError("word timestamps are not available in Vox Terminal")
