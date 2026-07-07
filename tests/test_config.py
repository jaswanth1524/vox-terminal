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
        self.assertIn("history_size = 20", example)
        self.assertIn("vad_auto_stop = true", example)
        self.assertIn("vad_silence_seconds = 1.0", example)

    def test_builds_whisper_prompt_from_initial_prompt_and_vocabulary(self) -> None:
        config = AppConfig(
            initial_prompt="Use terminal words.",
            custom_vocabulary=("Claude Code", "kubectl"),
        )

        self.assertEqual(
            config.whisper_initial_prompt,
            "Use terminal words. Vocabulary hints: Claude Code, kubectl.",
        )

    def test_loads_custom_vocabulary_from_toml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.toml"
            path.write_text(
                'custom_vocabulary = ["Claude Code", "FastAPI"]',
                encoding="utf-8",
            )
            config = load_config(path)

        self.assertEqual(config.custom_vocabulary, ("Claude Code", "FastAPI"))

    def test_rejects_non_list_custom_vocabulary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.toml"
            path.write_text('custom_vocabulary = "Claude Code"', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "custom_vocabulary"):
                load_config(path)

    def test_rejects_invalid_vad_timings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.toml"
            path.write_text("vad_silence_seconds = 0", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "vad_silence_seconds"):
                load_config(path)


if __name__ == "__main__":
    unittest.main()
