from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass

from pynput import keyboard

Callback = Callable[[], None]


@dataclass
class HotkeyCallbacks:
    on_press: Callback
    on_release: Callback
    on_no_events: Callback | None = None


class RightOptionHoldListener:
    def __init__(
        self,
        callbacks: HotkeyCallbacks,
        *,
        no_events_warning_seconds: float = 10.0,
    ) -> None:
        self.callbacks = callbacks
        self.no_events_warning_seconds = no_events_warning_seconds
        self._listener: keyboard.Listener | None = None
        self._warning_timer: threading.Timer | None = None
        self._pressed = False
        self._saw_event = threading.Event()

    def start(self) -> None:
        self._listener = keyboard.Listener(
            on_press=self._handle_press,
            on_release=self._handle_release,
        )
        self._listener.start()
        if self.callbacks.on_no_events is not None:
            self._warning_timer = threading.Timer(
                self.no_events_warning_seconds,
                self._warn_if_no_events,
            )
            self._warning_timer.daemon = True
            self._warning_timer.start()

    def stop(self) -> None:
        if self._warning_timer is not None:
            self._warning_timer.cancel()
            self._warning_timer = None
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
        self._pressed = False

    def join(self) -> None:
        if self._listener is not None:
            self._listener.join()

    def _handle_press(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        self._saw_event.set()
        if key != keyboard.Key.alt_r or self._pressed:
            return
        self._pressed = True
        self._run_callback("press", self.callbacks.on_press)

    def _handle_release(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        self._saw_event.set()
        if key != keyboard.Key.alt_r or not self._pressed:
            return
        self._pressed = False
        self._run_callback("release", self.callbacks.on_release)

    def _warn_if_no_events(self) -> None:
        if not self._saw_event.is_set() and self.callbacks.on_no_events is not None:
            self._run_callback("no-events warning", self.callbacks.on_no_events)

    @staticmethod
    def _run_callback(name: str, callback: Callback) -> None:
        try:
            callback()
        except Exception:
            # pynput stops dispatching when a callback raises. Keep the listener
            # alive so a transient recording/UI failure cannot strand the app in
            # the recording state.
            logging.exception("Unhandled hotkey %s callback failure", name)
