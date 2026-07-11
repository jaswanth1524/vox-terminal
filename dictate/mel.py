from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from typing import Any

import numpy as np


def mel_filterbank(
    *,
    sr: float,
    n_fft: int,
    n_mels: int = 128,
    fmin: float = 0.0,
    fmax: float | None = None,
    htk: bool = False,
    norm: str | float | None = "slaney",
    dtype: Any = np.float32,
) -> np.ndarray:
    """Build the Slaney mel filterbank Parakeet needs without librosa.

    This intentionally implements only the small, deterministic subset used by
    ``parakeet_mlx``. Keeping it local avoids importing Numba, SciPy, and
    scikit-learn into the resident app or frozen bundle.
    """

    if sr <= 0 or n_fft <= 0 or n_mels <= 0:
        raise ValueError("sr, n_fft, and n_mels must be positive")
    if htk:
        raise ValueError("HTK mel scaling is not supported")
    if norm not in {"slaney", None}:
        raise ValueError("only Slaney or no mel normalization is supported")
    fmax = sr / 2 if fmax is None else fmax
    if not 0 <= fmin < fmax <= sr / 2:
        raise ValueError("mel frequency range must fit within the Nyquist limit")

    fft_frequencies = np.linspace(0, sr / 2, 1 + n_fft // 2)
    mel_frequencies = _mel_to_hz(
        np.linspace(_hz_to_mel(fmin), _hz_to_mel(fmax), n_mels + 2)
    )
    frequency_diff = np.diff(mel_frequencies)
    ramps = mel_frequencies[:, np.newaxis] - fft_frequencies[np.newaxis, :]
    weights = np.zeros((n_mels, int(1 + n_fft // 2)))
    for index in range(n_mels):
        lower = -ramps[index] / frequency_diff[index]
        upper = ramps[index + 2] / frequency_diff[index + 1]
        weights[index] = np.maximum(0, np.minimum(lower, upper))

    if norm == "slaney":
        enorm = 2.0 / (mel_frequencies[2 : n_mels + 2] - mel_frequencies[:n_mels])
        weights *= enorm[:, np.newaxis]
    return weights.astype(dtype, copy=False)


def install_parakeet_librosa_shim() -> None:
    """Provide the one librosa API Parakeet uses before importing it."""

    shim = ModuleType("librosa")
    shim.filters = SimpleNamespace(mel=mel_filterbank)  # type: ignore[attr-defined]
    sys.modules["librosa"] = shim


def _hz_to_mel(frequencies: float | np.ndarray) -> float | np.ndarray:
    scalar = np.isscalar(frequencies)
    frequency_array = np.atleast_1d(np.asanyarray(frequencies, dtype=float))
    mels = 3.0 * frequency_array / 200.0
    log_region = frequency_array >= 1_000.0
    mels[log_region] = 15.0 + np.log(frequency_array[log_region] / 1_000.0) / (
        np.log(6.4) / 27.0
    )
    return float(mels[0]) if scalar else mels


def _mel_to_hz(mels: np.ndarray) -> np.ndarray:
    mels = np.asanyarray(mels, dtype=float)
    frequencies = 200.0 * mels / 3.0
    log_region = mels >= 15.0
    frequencies[log_region] = 1_000.0 * np.exp(
        (np.log(6.4) / 27.0) * (mels[log_region] - 15.0)
    )
    return frequencies
