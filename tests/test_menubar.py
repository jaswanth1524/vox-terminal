from __future__ import annotations

import unittest
from unittest import mock

from dictate.menubar import DictateMenuBar


class MissingModelService:
    def __init__(self, status_callback: object) -> None:
        self.status = "idle"
        self._status_callback = status_callback

    def apply_config(self, _config: object) -> bool:
        self.status = "model_missing"
        self._status_callback("model_missing")
        return False


class MenuHarness:
    def __init__(self) -> None:
        self.statuses: list[str] = []
        self.service = MissingModelService(self.set_status)
        self._runtime_error: str | None = None

    def set_status(self, status: str) -> None:
        self.statuses.append(status)

    def _record_runtime_error(self, context: str, exception: Exception) -> None:
        DictateMenuBar._record_runtime_error(self, context, exception)  # type: ignore[arg-type]


class MenuBarTests(unittest.TestCase):
    def test_uncached_model_selection_preserves_missing_status(self) -> None:
        menu = MenuHarness()

        DictateMenuBar._apply_settings(menu, object())  # type: ignore[arg-type]

        self.assertEqual(menu.statuses, ["model_missing"])

    @mock.patch("dictate.menubar.rumps.alert")
    def test_background_settings_failure_is_deferred_to_status_ui(
        self,
        alert: mock.Mock,
    ) -> None:
        menu = MenuHarness()
        menu.service.apply_config = mock.Mock(side_effect=RuntimeError("disk full"))

        with self.assertLogs(level="ERROR"):
            DictateMenuBar._apply_settings(menu, object())  # type: ignore[arg-type]

        self.assertEqual(menu.statuses, ["error"])
        self.assertIn("disk full", menu._runtime_error or "")
        alert.assert_not_called()

    def test_start_worker_contains_service_exception(self) -> None:
        menu = MenuHarness()
        menu.service.start = mock.Mock(side_effect=RuntimeError("load failed"))  # type: ignore[attr-defined]

        with self.assertLogs(level="ERROR"):
            DictateMenuBar._start_service(menu)  # type: ignore[arg-type]

        self.assertEqual(menu.statuses, ["error"])
        self.assertIn("load failed", menu._runtime_error or "")


if __name__ == "__main__":
    unittest.main()
