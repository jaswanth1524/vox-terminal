from __future__ import annotations

import subprocess
import threading
from contextlib import suppress

import rumps
from PyObjCTools import AppHelper

from . import autostart
from .doctor import check_accessibility, check_microphone
from .paths import DEFAULT_PATHS
from .settings import SettingsDialog

STATUS_TITLES = {
    "loading": "⏳",
    "checking_model": "⏳",
    "model_missing": "⚠️",
    "downloading_model": "⬇️",
    "warming_model": "⏳",
    "idle": "🎙️",
    "recording": "🔴",
    "transcribing": "⏳",
    "error": "⚠️",
    "stopped": "🎙️",
}

STATUS_LABELS = {
    "loading": "Loading model",
    "checking_model": "Checking model",
    "model_missing": "Model setup required",
    "downloading_model": "Downloading model",
    "warming_model": "Warming model",
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
        self._model_prompt_shown = False
        self._error_prompt_shown = False
        self.status_item = rumps.MenuItem("Status: Loading model")
        self.history_item = rumps.MenuItem("History", callback=self._show_history)
        self.clear_history_item = rumps.MenuItem(
            "Clear History",
            callback=self._clear_history,
        )
        self.performance_item = rumps.MenuItem(
            "Performance Report…", callback=self._show_performance
        )
        self.clear_performance_item = rumps.MenuItem(
            "Reset Performance Data…", callback=self._clear_performance
        )
        self.settings_item = rumps.MenuItem("Settings…", callback=self._show_settings)
        self.diagnostics_item = rumps.MenuItem(
            "Run Diagnostics…", callback=self._show_diagnostics
        )
        self.logs_item = rumps.MenuItem("Open Logs", callback=self._open_logs)
        self.login_item = rumps.MenuItem("Start at Login", callback=self._toggle_login)
        self.quit_item = rumps.MenuItem("Quit", callback=self._quit)
        self.menu = [
            self.status_item,
            None,
            self.history_item,
            self.clear_history_item,
            self.performance_item,
            self.clear_performance_item,
            None,
            self.settings_item,
            self.diagnostics_item,
            self.logs_item,
            None,
            self.login_item,
            self.quit_item,
        ]
        with suppress(Exception):
            autostart.migrate_legacy()
        self._refresh_login_item()

    def set_status(self, status: str) -> None:
        with self._status_lock:
            self._status = status
        AppHelper.callAfter(self._refresh_status, None)

    def run(self, **options: object) -> None:
        if hasattr(self.service, "set_status_callback"):
            self.service.set_status_callback(self.set_status)
        worker = threading.Thread(target=self._start_service, daemon=True)
        worker.start()
        super().run(**options)

    def _start_service(self) -> None:
        if hasattr(self.service, "start"):
            ok = self.service.start()
            if not ok and getattr(self.service, "status", "error") != "model_missing":
                self.set_status("error")

    def _refresh_status(self, _sender: rumps.Timer) -> None:
        with self._status_lock:
            status = self._status
        self.title = STATUS_TITLES.get(status, "🎙️")
        self.status_item.title = f"Status: {STATUS_LABELS.get(status, status)}"
        if status == "model_missing" and not self._model_prompt_shown:
            self._model_prompt_shown = True
            config = getattr(self.service, "config", None)
            engine = getattr(config, "engine", "speech")
            size = "about 2.3 GB" if engine == "parakeet" else "about 1.5 GB"
            response = rumps.alert(
                title="Set Up Vox Terminal",
                message=(
                    f"The {engine.title()} speech model is not installed. Download it "
                    f"once now ({size})? Normal dictation stays offline afterward."
                ),
                ok="Download Model",
                cancel="Quit",
            )
            if response == 1:
                threading.Thread(target=self._download_model, daemon=True).start()
            else:
                self._quit(self.quit_item)
        elif status == "error" and not self._error_prompt_shown:
            self._error_prompt_shown = True
            message = getattr(self.service, "last_error", None) or (
                "Vox Terminal needs attention. Run Diagnostics or open the logs for details."
            )
            rumps.alert(title="Vox Terminal", message=message)
        elif status == "idle":
            self._error_prompt_shown = False
            self._model_prompt_shown = False

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

    def _download_model(self) -> None:
        if hasattr(self.service, "download_and_start"):
            ok = self.service.download_and_start()
            if not ok:
                self.set_status("error")

    def _show_settings(self, _sender: rumps.MenuItem) -> None:
        config = getattr(self.service, "config", None)
        if config is None:
            return
        try:
            updated = SettingsDialog(config).run()
        except Exception as exc:
            rumps.alert(title="Vox Terminal", message=f"Could not open settings: {exc}")
            return
        if updated is None:
            return
        threading.Thread(
            target=self._apply_settings,
            args=(updated,),
            daemon=True,
        ).start()

    def _apply_settings(self, config: object) -> None:
        try:
            ok = self.service.apply_config(config)
        except Exception as exc:
            rumps.alert(title="Vox Terminal", message=f"Could not save settings: {exc}")
            return
        if not ok and getattr(self.service, "status", "error") != "model_missing":
            self.set_status("error")

    def _show_diagnostics(self, _sender: rumps.MenuItem) -> None:
        checks = [check_microphone(), check_accessibility()]
        lines = [f"{'✓' if passed else '⚠︎'} {message}" for passed, message in checks]
        lines.append("Input Monitoring is confirmed when the Right Option hotkey works.")
        response = rumps.alert(
            title="Vox Terminal Diagnostics",
            message="\n\n".join(lines),
            ok="Open Privacy Settings",
            cancel="Done",
        )
        if response == 1:
            subprocess.run(
                [
                    "open",
                    "x-apple.systempreferences:com.apple.preference.security?Privacy",
                ],
                check=False,
            )

    def _open_logs(self, _sender: rumps.MenuItem) -> None:
        DEFAULT_PATHS.logs.mkdir(parents=True, exist_ok=True)
        subprocess.run(["open", str(DEFAULT_PATHS.logs)], check=False)

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

    def _show_performance(self, _sender: rumps.MenuItem) -> None:
        text = "No latency samples yet."
        if hasattr(self.service, "performance_text"):
            text = self.service.performance_text()
        response = rumps.alert(
            title="Vox Terminal Performance",
            message=text,
            ok="Copy Report",
            cancel="Done",
        )
        if response == 1:
            subprocess.run(
                ["pbcopy"],
                input=text.encode("utf-8"),
                check=False,
            )

    def _clear_performance(self, _sender: rumps.MenuItem) -> None:
        response = rumps.alert(
            title="Reset Performance Data?",
            message=(
                "This removes the saved timing samples used by the Performance Report. "
                "No audio or transcript text is stored."
            ),
            ok="Reset",
            cancel="Cancel",
        )
        if response != 1:
            return
        if hasattr(self.service, "clear_performance_data"):
            self.service.clear_performance_data()
        rumps.notification(
            title="Vox Terminal",
            subtitle="Performance data reset",
            message="Saved latency timings were removed.",
        )

    def _quit(self, _sender: rumps.MenuItem) -> None:
        if hasattr(self.service, "stop"):
            self.service.stop()
        rumps.quit_application()
