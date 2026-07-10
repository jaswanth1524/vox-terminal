from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from enum import StrEnum

from .transcriber import Transcriber, configure_offline_mode


class ModelState(StrEnum):
    CHECKING = "checking_model"
    MISSING = "model_missing"
    DOWNLOADING = "downloading_model"
    WARMING = "warming_model"
    READY = "model_ready"
    ERROR = "error"


StateCallback = Callable[[ModelState], None]


@dataclass
class ModelManager:
    model: str
    language: str
    state_callback: StateCallback | None = None

    def _set_state(self, state: ModelState) -> None:
        if self.state_callback is not None:
            self.state_callback(state)

    def is_available(self) -> bool:
        """Return whether the complete model snapshot is already cached."""

        self._set_state(ModelState.CHECKING)
        try:
            from huggingface_hub import snapshot_download

            snapshot_download(repo_id=self.model, local_files_only=True)
        except Exception:
            self._set_state(ModelState.MISSING)
            return False
        self._set_state(ModelState.READY)
        return True

    def download(self) -> None:
        """Perform the one explicitly online operation used during onboarding."""

        self._set_state(ModelState.DOWNLOADING)
        configure_offline_mode(offline=False)
        try:
            from huggingface_hub import constants, snapshot_download

            # huggingface_hub reads this environment setting at import time;
            # update its cached flag for an in-process first-run transition.
            constants.HF_HUB_OFFLINE = False
            snapshot_download(repo_id=self.model, local_files_only=False)
            self._set_state(ModelState.WARMING)
            Transcriber(
                model=self.model,
                language=self.language,
                offline=True,
            ).load()
        except Exception:
            self._set_state(ModelState.ERROR)
            raise
        finally:
            configure_offline_mode(offline=True)
            with suppress(UnboundLocalError):
                constants.HF_HUB_OFFLINE = True
        self._set_state(ModelState.READY)
