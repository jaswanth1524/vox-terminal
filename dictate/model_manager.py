from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .network import (
    PROVISIONING_FLAG,
    install_offline_guard,
    is_provisioning_process,
    provisioning_environment,
)


class ModelState(StrEnum):
    CHECKING = "checking_model"
    MISSING = "model_missing"
    DOWNLOADING = "downloading_model"
    WARMING = "warming_model"
    READY = "model_ready"
    ERROR = "error"


class ModelProvisioningError(RuntimeError):
    pass


StateCallback = Callable[[ModelState], None]


def resolve_cached_model(model_id: str) -> Path | None:
    """Resolve a complete model snapshot without allowing a network fallback."""

    install_offline_guard()
    local_path = Path(model_id).expanduser()
    if local_path.exists():
        return local_path.resolve()
    try:
        from huggingface_hub import snapshot_download

        snapshot = snapshot_download(repo_id=model_id, local_files_only=True)
    except Exception:
        return None
    return Path(snapshot)


def provisioning_command(
    engine: str,
    model: str,
    language: str,
) -> list[str]:
    arguments = [
        PROVISIONING_FLAG,
        "--engine",
        engine,
        "--model",
        model,
        "--language",
        language,
    ]
    if getattr(sys, "frozen", False):
        return [sys.executable, *arguments]
    return [sys.executable, "-m", "dictate", *arguments]


def provision_model(engine: str, model: str, language: str) -> Path:
    """Download one model inside the explicitly authorized provisioning child."""

    if not is_provisioning_process():
        raise ModelProvisioningError("Refusing model download outside provisioning process")
    if engine not in {"whisper", "parakeet"}:
        raise ValueError(f"Unsupported transcription engine: {engine}")
    if not model.strip():
        raise ValueError("Model identifier must not be empty")
    if not language.strip():
        raise ValueError("Language must not be empty")

    from huggingface_hub import snapshot_download

    snapshot = snapshot_download(repo_id=model, local_files_only=False)
    return Path(snapshot)


@dataclass
class ModelManager:
    engine: str
    model: str
    language: str
    state_callback: StateCallback | None = None

    def _set_state(self, state: ModelState) -> None:
        if self.state_callback is not None:
            self.state_callback(state)

    def is_available(self) -> bool:
        """Return whether the complete model snapshot is already cached."""

        self._set_state(ModelState.CHECKING)
        if resolve_cached_model(self.model) is None:
            self._set_state(ModelState.MISSING)
            return False
        self._set_state(ModelState.READY)
        return True

    def download(self) -> Path:
        """Run the one explicitly online operation in a fresh child process."""

        install_offline_guard()
        self._set_state(ModelState.DOWNLOADING)
        command = provisioning_command(self.engine, self.model, self.language)
        try:
            subprocess.run(
                command,
                check=True,
                env=provisioning_environment(),
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            self._set_state(ModelState.ERROR)
            raise ModelProvisioningError(f"Model download process failed: {exc}") from exc

        snapshot = resolve_cached_model(self.model)
        if snapshot is None:
            self._set_state(ModelState.ERROR)
            raise ModelProvisioningError(
                "Model download finished, but the snapshot is not available in the local cache."
            )
        self._set_state(ModelState.READY)
        return snapshot
