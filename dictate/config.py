from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path
import tomllib
from typing import Any


CONFIG_PATH = Path("~/.config/dictate/config.toml").expanduser()
DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"


@dataclass(frozen=True)
class AppConfig:
    hotkey: str = "right_option"
    mode: str = "hold"
    model: str = DEFAULT_MODEL
    language: str = "en"
    sounds: bool = True
    paste_mode: str = "clipboard"
    restore_clipboard: bool = True
    min_recording_ms: int = 300
    max_recording_seconds: int = 120
    silence_rms_threshold: float = 0.002
    initial_prompt: str | None = None


def load_config(path: Path = CONFIG_PATH) -> AppConfig:
    if not path.exists():
        return AppConfig()

    with path.open("rb") as config_file:
        raw = tomllib.load(config_file)

    allowed = {field.name for field in fields(AppConfig)}
    unknown = sorted(set(raw) - allowed)
    if unknown:
        joined = ", ".join(unknown)
        raise ValueError(f"Unknown config key(s) in {path}: {joined}")

    config = AppConfig(**raw)
    _validate(config, path)
    return config


def _validate(config: AppConfig, path: Path) -> None:
    if config.hotkey != "right_option":
        raise ValueError(f"{path}: only hotkey = 'right_option' is supported")
    if config.mode not in {"hold", "toggle"}:
        raise ValueError(f"{path}: mode must be 'hold' or 'toggle'")
    if config.paste_mode not in {"clipboard", "keystroke"}:
        raise ValueError(f"{path}: paste_mode must be 'clipboard' or 'keystroke'")
    if config.min_recording_ms < 0:
        raise ValueError(f"{path}: min_recording_ms must be non-negative")
    if config.max_recording_seconds <= 0:
        raise ValueError(f"{path}: max_recording_seconds must be positive")
    if config.silence_rms_threshold < 0:
        raise ValueError(f"{path}: silence_rms_threshold must be non-negative")


def as_toml_example(config: AppConfig | None = None) -> str:
    config = config or AppConfig()
    values: dict[str, Any] = {
        "hotkey": config.hotkey,
        "mode": config.mode,
        "model": config.model,
        "language": config.language,
        "sounds": config.sounds,
        "paste_mode": config.paste_mode,
        "restore_clipboard": config.restore_clipboard,
        "min_recording_ms": config.min_recording_ms,
        "max_recording_seconds": config.max_recording_seconds,
    }
    lines = []
    for key, value in values.items():
        if isinstance(value, bool):
            rendered = "true" if value else "false"
        elif isinstance(value, int | float):
            rendered = str(value)
        else:
            rendered = f'"{value}"'
        lines.append(f"{key} = {rendered}")
    return "\n".join(lines) + "\n"
