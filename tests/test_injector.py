from __future__ import annotations

import unittest

from dictate.injector import ClipboardInjector, KeystrokeInjector, build_injector


class FakeTimer:
    def __init__(self, _delay: float, callback: object) -> None:
        self.callback = callback
        self.daemon = False
        self.cancelled = False

    def start(self) -> None:
        pass

    def cancel(self) -> None:
        self.cancelled = True

    def fire(self) -> None:
        if not self.cancelled:
            self.callback()


class MemoryClipboardInjector(ClipboardInjector):
    def __init__(self) -> None:
        self.clipboard = "original"
        self.pastes = 0
        self.timers: list[FakeTimer] = []
        super().__init__(timer_factory=self._timer)

    def _timer(self, delay: float, callback: object) -> FakeTimer:
        timer = FakeTimer(delay, callback)
        self.timers.append(timer)
        return timer

    def _read_clipboard_text(self) -> str:
        return self.clipboard

    def _write_clipboard_text(self, text: str) -> None:
        self.clipboard = text

    def _paste(self) -> None:
        self.pastes += 1


class InjectorTests(unittest.TestCase):
    def test_clipboard_restore_runs_after_inject_returns(self) -> None:
        injector = MemoryClipboardInjector()

        injector.inject("transcript")

        self.assertEqual(injector.clipboard, "transcript")
        self.assertEqual(injector.pastes, 1)
        injector.timers[-1].fire()
        self.assertEqual(injector.clipboard, "original")

    def test_restore_does_not_overwrite_new_user_clipboard(self) -> None:
        injector = MemoryClipboardInjector()
        injector.inject("transcript")
        injector.clipboard = "user copied this"

        injector.timers[-1].fire()

        self.assertEqual(injector.clipboard, "user copied this")

    def test_consecutive_injections_preserve_original_clipboard(self) -> None:
        injector = MemoryClipboardInjector()
        injector.inject("first")
        injector.inject("second")

        injector.timers[-1].fire()

        self.assertEqual(injector.clipboard, "original")
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
