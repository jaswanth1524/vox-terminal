from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from dictate.config import AppConfig, as_toml_example, load_config


class ConfigTests(unittest.TestCase):
    def test_allows_toggle_and_keystroke_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.toml"
            path.write_text(
                "\n".join(
                    [
                        'mode = "toggle"',
                        'paste_mode = "keystroke"',
                    ]
                ),
                encoding="utf-8",
            )
            config = load_config(path)

        self.assertEqual(config.mode, "toggle")
        self.assertEqual(config.paste_mode, "keystroke")

    def test_rejects_unknown_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.toml"
            path.write_text('unexpected = "value"', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Unknown config"):
                load_config(path)

    def test_example_includes_phase_2_controls(self) -> None:
        example = as_toml_example(AppConfig())
        self.assertIn('mode = "hold"', example)
        self.assertIn('paste_mode = "clipboard"', example)
        self.assertIn("max_recording_seconds = 120", example)


if __name__ == "__main__":
    unittest.main()
