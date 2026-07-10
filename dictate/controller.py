from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from .config import CONFIG_PATH, AppConfig, load_config, save_config
from .model_manager import ModelManager, ModelState

StatusCallback = Callable[[str], None]


class Service(Protocol):
    status: str

    def start(self) -> bool: ...

    def stop(self) -> None: ...

    def set_status_callback(self, callback: StatusCallback | None) -> None: ...

    def history_text(self) -> str: ...

    def clear_history(self) -> None: ...


ServiceFactory = Callable[[AppConfig], Service]
ModelManagerFactory = Callable[[str, str, Callable[[ModelState], None]], ModelManager]


def _default_service_factory(config: AppConfig) -> Service:
    from .__main__ import DictateService

    return DictateService(config)


def _default_model_manager_factory(
    model: str,
    language: str,
    callback: Callable[[ModelState], None],
) -> ModelManager:
    return ModelManager(model, language, callback)


@dataclass
class AppController:
    """Own model onboarding, service lifecycle, and persisted preferences."""

    config_path: Path = CONFIG_PATH
    service_factory: ServiceFactory = _default_service_factory
    model_manager_factory: ModelManagerFactory = _default_model_manager_factory
    config: AppConfig = field(init=False)
    last_error: str | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        self.config = load_config(self.config_path)
        self._service: Service | None = None
        self._status = "stopped"
        self._status_callback: StatusCallback | None = None
        self._lifecycle_lock = threading.Lock()

    @property
    def status(self) -> str:
        return self._status

    def set_status_callback(self, callback: StatusCallback | None) -> None:
        self._status_callback = callback
        if callback is not None:
            callback(self._status)

    def start(self) -> bool:
        """Start only when the configured model is already cached."""

        with self._lifecycle_lock:
            self.last_error = None
            manager = self._model_manager()
            if not manager.is_available():
                return False
            return self._start_service()

    def download_and_start(self) -> bool:
        """Download after explicit user consent, then start offline."""

        with self._lifecycle_lock:
            self.last_error = None
            try:
                self._model_manager().download()
            except Exception as exc:
                self.last_error = f"Model setup failed: {exc}"
                logging.exception(self.last_error)
                self._set_status("error")
                return False
            return self._start_service()

    def apply_config(self, config: AppConfig) -> bool:
        """Persist settings and restart the internal service with them."""

        with self._lifecycle_lock:
            save_config(config, self.config_path)
            self.config = config
            self._stop_service()
            self.last_error = None
            if not self._model_manager().is_available():
                return False
            return self._start_service()

    def stop(self) -> None:
        with self._lifecycle_lock:
            self._stop_service()
            self._set_status("stopped")

    def history_text(self) -> str:
        if self._service is None:
            return "No transcript history yet."
        return self._service.history_text()

    def clear_history(self) -> None:
        if self._service is not None:
            self._service.clear_history()

    def _model_manager(self) -> ModelManager:
        return self.model_manager_factory(
            self.config.model,
            self.config.language,
            self._set_model_state,
        )

    def _start_service(self) -> bool:
        self._stop_service()
        service = self.service_factory(self.config)
        service.set_status_callback(self._set_status)
        self._service = service
        if service.start():
            return True
        self.last_error = getattr(service, "last_error", None) or "Vox Terminal could not start."
        self._set_status("error")
        return False

    def _stop_service(self) -> None:
        if self._service is not None:
            self._service.stop()
            self._service = None

    def _set_model_state(self, state: ModelState) -> None:
        if state == ModelState.READY:
            return
        self._set_status(str(state))

    def _set_status(self, status: str) -> None:
        self._status = status
        if self._status_callback is not None:
            self._status_callback(status)
