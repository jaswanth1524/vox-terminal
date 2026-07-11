from __future__ import annotations

import json
import os
import tempfile
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

from .paths import DEFAULT_PATHS

CONFIG_PATH = DEFAULT_PATHS.config
DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"
DEFAULT_PARAKEET_MODEL = "mlx-community/parakeet-tdt-0.6b-v2"
DEFAULT_PARAKEET_BEAM_SIZE = 2


@dataclass(frozen=True)
class AppConfig:
    engine: str = "parakeet"
    hotkey: str = "right_option"
    mode: str = "hold"
    model: str = DEFAULT_MODEL
    parakeet_model: str = DEFAULT_PARAKEET_MODEL
    parakeet_beam_size: int = DEFAULT_PARAKEET_BEAM_SIZE
    parakeet_quantization_bits: int = 3
    language: str = "en"
    sounds: bool = True
    paste_mode: str = "clipboard"
    restore_clipboard: bool = True
    min_recording_ms: int = 300
    max_recording_seconds: int = 120
    silence_rms_threshold: float = 0.002
    initial_prompt: str | None = None
    custom_vocabulary: tuple[str, ...] = ()
    history_size: int = 20
    vad_auto_stop: bool = True
    vad_silence_seconds: float = 1.0
    vad_min_speech_seconds: float = 0.25
    vad_poll_seconds: float = 0.25

    @property
    def whisper_initial_prompt(self) -> str | None:
        parts: list[str] = []
        if self.initial_prompt:
            parts.append(self.initial_prompt.strip())
        if self.custom_vocabulary:
            terms = ", ".join(self.custom_vocabulary)
            parts.append(f"Vocabulary hints: {terms}.")
        prompt = " ".join(part for part in parts if part)
        return prompt or None

    @property
    def selected_model(self) -> str:
        return self.parakeet_model if self.engine == "parakeet" else self.model


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

    if "custom_vocabulary" in raw and isinstance(raw["custom_vocabulary"], list):
        raw["custom_vocabulary"] = tuple(
            term.strip() if isinstance(term, str) else term
            for term in raw["custom_vocabulary"]
        )

    config = AppConfig(**raw)
    validate_config(config, path)
    return config


def validate_config(config: AppConfig, path: Path = CONFIG_PATH) -> None:
    if config.engine not in {"whisper", "parakeet"}:
        raise ValueError(f"{path}: engine must be 'whisper' or 'parakeet'")
    if config.hotkey != "right_option":
        raise ValueError(f"{path}: only hotkey = 'right_option' is supported")
    if config.parakeet_beam_size < 1 or config.parakeet_beam_size > 5:
        raise ValueError(f"{path}: parakeet_beam_size must be between 1 and 5")
    if config.parakeet_quantization_bits not in {0, 3, 4, 8}:
        raise ValueError(f"{path}: parakeet_quantization_bits must be 0, 3, 4, or 8")
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
    if not isinstance(config.custom_vocabulary, tuple):
        raise ValueError(f"{path}: custom_vocabulary must be a list of strings")
    if not all(isinstance(term, str) and term.strip() for term in config.custom_vocabulary):
        raise ValueError(f"{path}: custom_vocabulary must contain only non-empty strings")
    if config.history_size < 0:
        raise ValueError(f"{path}: history_size must be non-negative")
    if config.vad_silence_seconds <= 0:
        raise ValueError(f"{path}: vad_silence_seconds must be positive")
    if config.vad_min_speech_seconds < 0:
        raise ValueError(f"{path}: vad_min_speech_seconds must be non-negative")
    if config.vad_poll_seconds <= 0:
        raise ValueError(f"{path}: vad_poll_seconds must be positive")


def as_toml(config: AppConfig | None = None) -> str:
    config = config or AppConfig()
    values: dict[str, Any] = {
        "engine": config.engine,
        "hotkey": config.hotkey,
        "mode": config.mode,
        "model": config.model,
        "parakeet_model": config.parakeet_model,
        "parakeet_beam_size": config.parakeet_beam_size,
        "parakeet_quantization_bits": config.parakeet_quantization_bits,
        "language": config.language,
        "sounds": config.sounds,
        "paste_mode": config.paste_mode,
        "restore_clipboard": config.restore_clipboard,
        "min_recording_ms": config.min_recording_ms,
        "max_recording_seconds": config.max_recording_seconds,
        "silence_rms_threshold": config.silence_rms_threshold,
        "initial_prompt": config.initial_prompt,
        "history_size": config.history_size,
        "vad_auto_stop": config.vad_auto_stop,
        "vad_silence_seconds": config.vad_silence_seconds,
        "vad_min_speech_seconds": config.vad_min_speech_seconds,
        "vad_poll_seconds": config.vad_poll_seconds,
    }
    lines = []
    for key, value in values.items():
        if value is None:
            continue
        if isinstance(value, bool):
            rendered = "true" if value else "false"
        elif isinstance(value, int | float):
            rendered = str(value)
        else:
            rendered = json.dumps(value, ensure_ascii=False)
        lines.append(f"{key} = {rendered}")
    if config.custom_vocabulary:
        quoted = ", ".join(
            json.dumps(term, ensure_ascii=False) for term in config.custom_vocabulary
        )
        lines.append(f"custom_vocabulary = [{quoted}]")
    return "\n".join(lines) + "\n"


def as_toml_example(config: AppConfig | None = None) -> str:
    return as_toml(config)


def save_config(config: AppConfig, path: Path = CONFIG_PATH) -> None:
    """Validate and atomically persist configuration without partial writes."""

    validate_config(config, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as config_file:
            config_file.write(as_toml(config))
            config_file.flush()
            os.fsync(config_file.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)
