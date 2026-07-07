from __future__ import annotations

import threading

import rumps

from . import autostart


STATUS_TITLES = {
    "loading": "⏳",
    "idle": "🎙️",
    "recording": "🔴",
    "transcribing": "⏳",
    "error": "⚠️",
    "stopped": "🎙️",
}

STATUS_LABELS = {
    "loading": "Loading model",
    "idle": "Idle",
    "recording": "Recording",
    "transcribing": "Transcribing",
    "error": "Needs attention",
    "stopped": "Stopped",
}


class DictateMenuBar(rumps.App):
    def __init__(self, service: object) -> None:
        super().__init__("🎙️", quit_button=None)
        self.service = service
        self._status = "loading"
        self._status_lock = threading.Lock()
        self.status_item = rumps.MenuItem("Status: Loading model")
        self.history_item = rumps.MenuItem("History", callback=self._show_history)
        self.clear_history_item = rumps.MenuItem(
            "Clear History",
            callback=self._clear_history,
        )
        self.login_item = rumps.MenuItem("Start at Login", callback=self._toggle_login)
        self.quit_item = rumps.MenuItem("Quit", callback=self._quit)
        self.menu = [
            self.status_item,
            None,
            self.history_item,
            self.clear_history_item,
            None,
            self.login_item,
            self.quit_item,
        ]
        self._refresh_login_item()
        self._timer = rumps.Timer(self._refresh_status, 0.25)
        self._timer.start()

    def set_status(self, status: str) -> None:
        with self._status_lock:
            self._status = status

    def run(self, **options: object) -> None:
        if hasattr(self.service, "set_status_callback"):
            self.service.set_status_callback(self.set_status)
        worker = threading.Thread(target=self._start_service, daemon=True)
        worker.start()
        super().run(**options)

    def _start_service(self) -> None:
        if hasattr(self.service, "start"):
            ok = self.service.start()
            if not ok:
                self.set_status("error")

    def _refresh_status(self, _sender: rumps.Timer) -> None:
        with self._status_lock:
            status = self._status
        self.title = STATUS_TITLES.get(status, "🎙️")
        self.status_item.title = f"Status: {STATUS_LABELS.get(status, status)}"

    def _refresh_login_item(self) -> None:
        self.login_item.state = 1 if autostart.is_enabled() else 0

    def _toggle_login(self, _sender: rumps.MenuItem) -> None:
        try:
            if autostart.is_enabled():
                autostart.disable()
            else:
                autostart.enable()
            self._refresh_login_item()
        except Exception as exc:
            rumps.alert(
                title="Vox Terminal",
                message=f"Could not update Start at Login: {exc}",
            )

    def _show_history(self, _sender: rumps.MenuItem) -> None:
        text = "No transcript history yet."
        if hasattr(self.service, "history_text"):
            text = self.service.history_text()
        rumps.alert(title="Vox Terminal History", message=text)

    def _clear_history(self, _sender: rumps.MenuItem) -> None:
        if hasattr(self.service, "clear_history"):
            self.service.clear_history()
        rumps.notification(
            title="Vox Terminal",
            subtitle="History cleared",
            message="Transcript history was cleared.",
        )

    def _quit(self, _sender: rumps.MenuItem) -> None:
        if hasattr(self.service, "stop"):
            self.service.stop()
        rumps.quit_application()
