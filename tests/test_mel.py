from __future__ import annotations

import sys
import unittest

import numpy as np

from dictate.mel import install_parakeet_librosa_shim, mel_filterbank


class MelFilterbankTests(unittest.TestCase):
    def test_matches_reference_slaney_filterbank(self) -> None:
        expected = np.array(
            [
                [0, 0.001428778, 0.000534866, 0, 0, 0, 0, 0, 0],
                [0, 0, 0.000851009, 0.000864714, 0.000234111, 0, 0, 0, 0],
                [
                    0,
                    0,
                    0,
                    0.000219846,
                    0.000579353,
                    0.000589309,
                    0.000392873,
                    0.000196436,
                    0,
                ],
            ],
            dtype=np.float32,
        )

        actual = mel_filterbank(sr=8_000, n_fft=16, n_mels=3, fmax=4_000)

        np.testing.assert_allclose(actual, expected, rtol=1e-5, atol=1e-8)

    def test_installs_minimal_parakeet_compatibility_module(self) -> None:
        original = sys.modules.get("librosa")
        try:
            install_parakeet_librosa_shim()

            import librosa

            self.assertIs(librosa.filters.mel, mel_filterbank)
        finally:
            if original is None:
                sys.modules.pop("librosa", None)
            else:
                sys.modules["librosa"] = original


if __name__ == "__main__":
    unittest.main()
