from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    """Filesystem locations used by Vox Terminal.

    Config stays at the historical path so existing installations continue to
    work. Logs use the conventional macOS user Library location.
    """

    config: Path = Path("~/.config/dictate/config.toml").expanduser()
    logs: Path = Path("~/Library/Logs/Vox Terminal").expanduser()
    application_support: Path = Path(
        "~/Library/Application Support/Vox Terminal"
    ).expanduser()

    @property
    def log_file(self) -> Path:
        return self.logs / "vox-terminal.log"

    @property
    def latency_file(self) -> Path:
        return self.application_support / "latency.json"


DEFAULT_PATHS = AppPaths()
