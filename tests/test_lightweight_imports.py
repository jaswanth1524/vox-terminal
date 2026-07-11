from __future__ import annotations

import sys
import unittest

from dictate.lightweight_imports import install_whisper_timing_shims


class LightweightImportTests(unittest.TestCase):
    def test_installs_identity_numba_decorator_for_disabled_timing_path(self) -> None:
        originals = {
            name: sys.modules.get(name)
            for name in ("numba", "scipy", "scipy.signal")
        }
        try:
            install_whisper_timing_shims()
            import numba

            @numba.jit(nopython=True)
            def add_one(value: int) -> int:
                return value + 1

            self.assertEqual(add_one(2), 3)
        finally:
            for name, module in originals.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module

    def test_word_timing_stub_fails_closed_if_accidentally_enabled(self) -> None:
        originals = {
            name: sys.modules.get(name)
            for name in ("numba", "scipy", "scipy.signal")
        }
        try:
            install_whisper_timing_shims()
            from scipy import signal

            with self.assertRaisesRegex(RuntimeError, "word timestamps"):
                signal.medfilt([])
        finally:
            for name, module in originals.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module


if __name__ == "__main__":
    unittest.main()
