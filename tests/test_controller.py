from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from dictate.config import AppConfig, load_config
from dictate.controller import AppController
from dictate.model_manager import ModelState


class FakeService:
    def __init__(self, config: AppConfig, *, starts: bool = True) -> None:
        self.config = config
        self.starts = starts
        self.status = "stopped"
        self.stops = 0
        self.callback = None

    def set_status_callback(self, callback: object) -> None:
        self.callback = callback

    def start(self) -> bool:
        if self.starts:
            self.status = "idle"
            if self.callback:
                self.callback("idle")
        return self.starts

    def stop(self) -> None:
        self.stops += 1
        self.status = "stopped"

    def history_text(self) -> str:
        return "history"

    def clear_history(self) -> None:
        pass


class FakeModelManager:
    def __init__(self, available: bool, callback: object) -> None:
        self.available = available
        self.callback = callback
        self.downloads = 0

    def is_available(self) -> bool:
        if not self.available:
            self.callback(ModelState.MISSING)
        return self.available

    def download(self) -> None:
        self.downloads += 1
        self.available = True
        self.callback(ModelState.READY)


class ControllerTests(unittest.TestCase):
    def test_missing_model_is_exposed_without_starting_service(self) -> None:
        services: list[FakeService] = []

        with tempfile.TemporaryDirectory() as temp_dir:
            controller = AppController(
                config_path=Path(temp_dir) / "config.toml",
                service_factory=lambda config: services.append(FakeService(config)) or services[-1],
                model_manager_factory=lambda _model, _language, callback: FakeModelManager(
                    False, callback
                ),
            )

            self.assertFalse(controller.start())

        self.assertEqual(controller.status, "model_missing")
        self.assertEqual(services, [])

    def test_apply_config_persists_and_restarts_service(self) -> None:
        services: list[FakeService] = []
        manager = FakeModelManager(True, lambda _state: None)

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.toml"
            controller = AppController(
                config_path=path,
                service_factory=lambda config: services.append(FakeService(config)) or services[-1],
                model_manager_factory=lambda _model, _language, callback: manager,
            )
            self.assertTrue(controller.start())

            self.assertTrue(controller.apply_config(AppConfig(mode="toggle")))

            self.assertEqual(load_config(path).mode, "toggle")
            self.assertEqual(len(services), 2)
            self.assertEqual(services[0].stops, 1)
            self.assertEqual(controller.status, "idle")


if __name__ == "__main__":
    unittest.main()
