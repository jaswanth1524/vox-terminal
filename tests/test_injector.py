from __future__ import annotations

import unittest

from dictate.injector import ClipboardInjector, KeystrokeInjector, build_injector


class InjectorTests(unittest.TestCase):
    def test_builds_clipboard_injector_by_default(self) -> None:
        injector = build_injector(paste_mode="clipboard", restore_clipboard=True)
        self.assertIsInstance(injector, ClipboardInjector)

    def test_builds_keystroke_injector_fallback(self) -> None:
        injector = build_injector(paste_mode="keystroke", restore_clipboard=True)
        self.assertIsInstance(injector, KeystrokeInjector)

    def test_rejects_unknown_mode(self) -> None:
        with self.assertRaises(ValueError):
            build_injector(paste_mode="invalid", restore_clipboard=True)


if __name__ == "__main__":
    unittest.main()
