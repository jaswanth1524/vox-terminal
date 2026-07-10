from __future__ import annotations

import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from Quartz import (
    CGEventCreateKeyboardEvent,
    CGEventKeyboardSetUnicodeString,
    CGEventPost,
    CGEventSetFlags,
    kCGEventFlagMaskCommand,
    kCGHIDEventTap,
)

V_KEY_CODE = 9


class InjectionError(RuntimeError):
    pass


class TextInjector(Protocol):
    def inject(self, text: str) -> None:
        pass


def build_injector(*, paste_mode: str, restore_clipboard: bool) -> TextInjector:
    if paste_mode == "clipboard":
        return ClipboardInjector(restore_clipboard=restore_clipboard)
    if paste_mode == "keystroke":
        return KeystrokeInjector()
    raise ValueError(f"Unsupported paste_mode: {paste_mode}")


@dataclass
class ClipboardInjector:
    restore_clipboard: bool = True
    restore_delay_seconds: float = 0.3
    timer_factory: Callable[[float, Callable[[], None]], Any] = threading.Timer
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _restore_timer: Any | None = field(default=None, init=False)
    _original_clipboard: str | None = field(default=None, init=False)

    def inject(self, text: str) -> None:
        if not text:
            return

        with self._lock:
            previous = self._prepare_previous_clipboard()
            try:
                self._write_clipboard_text(text)
                self._paste()
                if self.restore_clipboard:
                    self._schedule_restore(original=previous, transcript=text)
            except Exception as exc:
                if self.restore_clipboard:
                    self._write_clipboard_text(previous)
                raise InjectionError(f"Could not paste transcript: {exc}") from exc

    def _prepare_previous_clipboard(self) -> str:
        if self._restore_timer is not None:
            self._restore_timer.cancel()
            self._restore_timer = None
            if self._original_clipboard is not None:
                return self._original_clipboard
        return self._read_clipboard_text()

    def _schedule_restore(self, *, original: str, transcript: str) -> None:
        self._original_clipboard = original

        def restore() -> None:
            with self._lock:
                try:
                    if self._read_clipboard_text() == transcript:
                        self._write_clipboard_text(original)
                finally:
                    self._restore_timer = None
                    self._original_clipboard = None

        timer = self.timer_factory(self.restore_delay_seconds, restore)
        timer.daemon = True
        self._restore_timer = timer
        timer.start()

    def _read_clipboard_text(self) -> str:
        result = subprocess.run(
            ["pbpaste"],
            check=False,
            capture_output=True,
        )
        if result.returncode != 0:
            return ""
        return result.stdout.decode("utf-8", errors="replace")

    def _write_clipboard_text(self, text: str) -> None:
        subprocess.run(
            ["pbcopy"],
            input=text.encode("utf-8"),
            check=True,
            capture_output=True,
        )

    def _paste(self) -> None:
        key_down = CGEventCreateKeyboardEvent(None, V_KEY_CODE, True)
        key_up = CGEventCreateKeyboardEvent(None, V_KEY_CODE, False)
        if key_down is None or key_up is None:
            raise InjectionError("Quartz could not create keyboard events")
        CGEventSetFlags(key_down, kCGEventFlagMaskCommand)
        CGEventSetFlags(key_up, kCGEventFlagMaskCommand)
        CGEventPost(kCGHIDEventTap, key_down)
        CGEventPost(kCGHIDEventTap, key_up)


@dataclass
class KeystrokeInjector:
    key_delay_seconds: float = 0.001

    def inject(self, text: str) -> None:
        if not text:
            return
        try:
            for character in text:
                self._type_character(character)
                if self.key_delay_seconds:
                    time.sleep(self.key_delay_seconds)
        except Exception as exc:
            raise InjectionError(f"Could not type transcript: {exc}") from exc

    def _type_character(self, character: str) -> None:
        key_down = CGEventCreateKeyboardEvent(None, 0, True)
        key_up = CGEventCreateKeyboardEvent(None, 0, False)
        if key_down is None or key_up is None:
            raise InjectionError("Quartz could not create keyboard events")
        CGEventKeyboardSetUnicodeString(key_down, len(character), character)
        CGEventKeyboardSetUnicodeString(key_up, len(character), character)
        CGEventPost(kCGHIDEventTap, key_down)
        CGEventPost(kCGHIDEventTap, key_up)
