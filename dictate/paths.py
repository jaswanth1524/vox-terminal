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

    @property
    def log_file(self) -> Path:
        return self.logs / "vox-terminal.log"


DEFAULT_PATHS = AppPaths()
