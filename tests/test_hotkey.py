from __future__ import annotations

import unittest
from unittest import mock

from pynput import keyboard

from dictate.hotkey import HotkeyCallbacks, RightOptionHoldListener


class HotkeyTests(unittest.TestCase):
    def test_callback_failure_does_not_break_later_hotkey_events(self) -> None:
        releases: list[str] = []

        def fail_press() -> None:
            raise RuntimeError("transient press failure")

        listener = RightOptionHoldListener(
            HotkeyCallbacks(
                on_press=fail_press,
                on_release=lambda: releases.append("released"),
            )
        )

        with self.assertLogs(level="ERROR") as captured:
            listener._handle_press(keyboard.Key.alt_r)
            listener._handle_release(keyboard.Key.alt_r)

        self.assertEqual(releases, ["released"])
        self.assertIn("transient press failure", "\n".join(captured.output))

    def test_stop_cancels_warning_and_resets_pressed_state(self) -> None:
        listener = RightOptionHoldListener(HotkeyCallbacks(lambda: None, lambda: None))
        warning_timer = mock.Mock()
        native_listener = mock.Mock()
        listener._warning_timer = warning_timer
        listener._listener = native_listener
        listener._pressed = True

        listener.stop()

        warning_timer.cancel.assert_called_once_with()
        native_listener.stop.assert_called_once_with()
        self.assertFalse(listener._pressed)
        self.assertIsNone(listener._listener)


if __name__ == "__main__":
    unittest.main()
