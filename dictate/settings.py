from __future__ import annotations

from dataclasses import replace

from AppKit import (
    NSApp,
    NSBackingStoreBuffered,
    NSButton,
    NSMakeRect,
    NSPopUpButton,
    NSScrollView,
    NSSwitchButton,
    NSTextField,
    NSTextView,
    NSWindow,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskTitled,
)
from Foundation import NSObject

from .config import AppConfig, validate_config

ENGINE_TITLES = {
    "parakeet": "Parakeet — Fast English",
    "whisper": "Whisper — Multilingual",
}


def _label(text: str, x: float, y: float, width: float = 130) -> NSTextField:
    label = NSTextField.labelWithString_(text)
    label.setFrame_(NSMakeRect(x, y, width, 24))
    return label


class _SettingsActions(NSObject):
    def initWithDialog_(self, dialog: SettingsDialog) -> _SettingsActions:
        self = self.init()
        if self is not None:
            self.dialog = dialog
        return self

    def save_(self, _sender: object) -> None:
        self.dialog.accepted = True
        NSApp.stopModalWithCode_(1)

    def cancel_(self, _sender: object) -> None:
        NSApp.stopModalWithCode_(0)


class SettingsDialog:
    """Small native preferences window for frequently changed settings."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.accepted = False
        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, 500, 474),
            NSWindowStyleMaskTitled | NSWindowStyleMaskClosable,
            NSBackingStoreBuffered,
            False,
        )
        self.window.setTitle_("Vox Terminal Settings")
        self.window.center()
        content = self.window.contentView()

        content.addSubview_(_label("Speech engine", 24, 418))
        self.engine = NSPopUpButton.alloc().initWithFrame_pullsDown_(
            NSMakeRect(170, 418, 290, 26), False
        )
        self.engine.addItemsWithTitles_(list(ENGINE_TITLES.values()))
        self.engine.selectItemWithTitle_(ENGINE_TITLES[config.engine])
        content.addSubview_(self.engine)

        content.addSubview_(_label("Recording mode", 24, 374))
        self.mode = NSPopUpButton.alloc().initWithFrame_pullsDown_(
            NSMakeRect(170, 374, 290, 26), False
        )
        self.mode.addItemsWithTitles_(["Hold", "Toggle"])
        self.mode.selectItemWithTitle_(config.mode.title())
        content.addSubview_(self.mode)

        content.addSubview_(_label("Language", 24, 330))
        self.language = NSTextField.alloc().initWithFrame_(NSMakeRect(170, 330, 290, 24))
        self.language.setStringValue_(config.language)
        self.language.setPlaceholderString_("en")
        content.addSubview_(self.language)

        content.addSubview_(_label("Paste method", 24, 286))
        self.paste_mode = NSPopUpButton.alloc().initWithFrame_pullsDown_(
            NSMakeRect(170, 286, 290, 26), False
        )
        self.paste_mode.addItemsWithTitles_(["Clipboard", "Keystroke"])
        self.paste_mode.selectItemWithTitle_(config.paste_mode.title())
        content.addSubview_(self.paste_mode)

        self.sounds = self._checkbox("Play start and stop sounds", 170, 244, config.sounds)
        self.restore = self._checkbox(
            "Restore text clipboard after pasting", 170, 208, config.restore_clipboard
        )
        content.addSubview_(self.sounds)
        content.addSubview_(self.restore)

        content.addSubview_(_label("Vocabulary", 24, 162))
        hint = _label("One term per line", 24, 138)
        hint.setTextColor_(hint.textColor().colorWithAlphaComponent_(0.65))
        content.addSubview_(hint)
        scroll = NSScrollView.alloc().initWithFrame_(NSMakeRect(170, 104, 290, 82))
        scroll.setHasVerticalScroller_(True)
        self.vocabulary = NSTextView.alloc().initWithFrame_(NSMakeRect(0, 0, 276, 82))
        self.vocabulary.setString_("\n".join(config.custom_vocabulary))
        scroll.setDocumentView_(self.vocabulary)
        content.addSubview_(scroll)

        self.actions = _SettingsActions.alloc().initWithDialog_(self)
        cancel = self._button("Cancel", 292, 28, "cancel:")
        save = self._button("Save & Restart", 372, 28, "save:", width=88)
        save.setKeyEquivalent_("\r")
        content.addSubview_(cancel)
        content.addSubview_(save)

    def _checkbox(self, title: str, x: float, y: float, enabled: bool) -> NSButton:
        button = NSButton.alloc().initWithFrame_(NSMakeRect(x, y, 290, 24))
        button.setButtonType_(NSSwitchButton)
        button.setTitle_(title)
        button.setState_(1 if enabled else 0)
        return button

    def _button(
        self,
        title: str,
        x: float,
        y: float,
        action: str,
        *,
        width: float = 70,
    ) -> NSButton:
        button = NSButton.alloc().initWithFrame_(NSMakeRect(x, y, width, 30))
        button.setTitle_(title)
        button.setBezelStyle_(1)
        button.setTarget_(self.actions)
        button.setAction_(action)
        return button

    def run(self) -> AppConfig | None:
        NSApp.runModalForWindow_(self.window)
        self.window.orderOut_(None)
        if not self.accepted:
            return None
        vocabulary = tuple(
            term.strip()
            for term in str(self.vocabulary.string()).splitlines()
            if term.strip()
        )
        updated = replace(
            self.config,
            engine=next(
                key
                for key, title in ENGINE_TITLES.items()
                if title == str(self.engine.titleOfSelectedItem())
            ),
            mode=str(self.mode.titleOfSelectedItem()).lower(),
            language=str(self.language.stringValue()).strip() or "en",
            paste_mode=str(self.paste_mode.titleOfSelectedItem()).lower(),
            sounds=bool(self.sounds.state()),
            restore_clipboard=bool(self.restore.state()),
            custom_vocabulary=vocabulary,
        )
        validate_config(updated)
        return updated
