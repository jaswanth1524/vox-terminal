from __future__ import annotations

from dataclasses import dataclass
import subprocess
import time
from typing import Protocol

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

    def inject(self, text: str) -> None:
        if not text:
            return

        previous = self._read_clipboard_text()
        try:
            self._write_clipboard_text(text)
            self._paste()
            time.sleep(self.restore_delay_seconds)
        except Exception as exc:
            raise InjectionError(f"Could not paste transcript: {exc}") from exc
        finally:
            if self.restore_clipboard:
                self._write_clipboard_text(previous)

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
