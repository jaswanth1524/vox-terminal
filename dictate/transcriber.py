from __future__ import annotations

import argparse
import gc
import os
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .config import DEFAULT_MODEL
from .lightweight_imports import install_whisper_timing_shims

TranscribeImpl = Callable[..., Mapping[str, Any]]


class ModelUnavailableError(RuntimeError):
    pass


def configure_offline_mode(*, offline: bool = True) -> None:
    if offline:
        from .network import install_offline_guard

        install_offline_guard()
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_DATASETS_OFFLINE"] = "1"
    else:
        for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE"):
            os.environ.pop(key, None)

    # huggingface_hub caches this value at import time. The onboarding cache
    # check imports it before the transcriber is constructed, so keep the
    # in-memory flag synchronized with the environment.
    hub_constants = sys.modules.get("huggingface_hub.constants")
    if hub_constants is not None:
        hub_constants.HF_HUB_OFFLINE = offline


def _default_transcribe_impl(audio: str | np.ndarray, **kwargs: Any) -> Mapping[str, Any]:
    install_whisper_timing_shims()
    import mlx_whisper

    return mlx_whisper.transcribe(audio, **kwargs)


@dataclass
class Transcriber:
    model: str = DEFAULT_MODEL
    language: str = "en"
    initial_prompt: str | None = None
    offline: bool = True
    temperature: float = 0.0
    transcribe_impl: TranscribeImpl = _default_transcribe_impl
    name: str = field(default="whisper", init=False)
    _loaded: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        configure_offline_mode(offline=self.offline)

    def load(self) -> None:
        if self._loaded:
            return
        silent_warmup = np.zeros(16_000, dtype=np.float32)
        try:
            self._call_backend(silent_warmup)
        except Exception as exc:
            if self.offline:
                from .model_manager import resolve_cached_model

                if resolve_cached_model(self.model) is None:
                    raise ModelUnavailableError(
                        "Model is not available in the local cache. Use the app's "
                        "Download Model prompt, or select it in the configuration and run "
                        "`uv run python -m dictate --download-model`."
                    ) from exc
            raise
        self._loaded = True

    def transcribe(self, audio: str | np.ndarray) -> str:
        self.load()
        result = self._call_backend(audio)
        text = result.get("text", "")
        return str(text)

    def close(self) -> None:
        self._loaded = False
        if self.transcribe_impl is not _default_transcribe_impl:
            return
        try:
            import mlx.core as mx
            from mlx_whisper.transcribe import ModelHolder

            ModelHolder.model = None
            ModelHolder.model_path = None
            gc.collect()
            mx.clear_cache()
        except (ImportError, RuntimeError):
            pass

    def _call_backend(self, audio: str | np.ndarray) -> Mapping[str, Any]:
        return self.transcribe_impl(
            audio,
            path_or_hf_repo=self.model,
            language=self.language,
            verbose=None,
            condition_on_previous_text=False,
            initial_prompt=self.initial_prompt,
            temperature=self.temperature,
        )


def download_model(model: str = DEFAULT_MODEL, language: str = "en") -> None:
    from .model_manager import ModelManager

    ModelManager("whisper", model, language).download()


def main() -> int:
    parser = argparse.ArgumentParser(description="Vox Terminal transcriber utilities")
    parser.add_argument("--download-model", action="store_true")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--language", default="en")
    args = parser.parse_args()

    if args.download_model:
        print(f"Downloading and warming model: {args.model}")
        download_model(model=args.model, language=args.language)
        print("Model is available in the local cache.")
        return 0

    parser.error("No action requested")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
