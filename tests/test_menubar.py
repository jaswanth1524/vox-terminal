from __future__ import annotations

import unittest

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

    def set_status(self, status: str) -> None:
        self.statuses.append(status)


class MenuBarTests(unittest.TestCase):
    def test_uncached_model_selection_preserves_missing_status(self) -> None:
        menu = MenuHarness()

        DictateMenuBar._apply_settings(menu, object())  # type: ignore[arg-type]

        self.assertEqual(menu.statuses, ["model_missing"])


if __name__ == "__main__":
    unittest.main()
