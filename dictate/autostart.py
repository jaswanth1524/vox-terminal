from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import sys


LABEL = "com.user.dictate"
TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "scripts" / f"{LABEL}.plist"
DESTINATION_PATH = Path("~/Library/LaunchAgents").expanduser() / f"{LABEL}.plist"


@dataclass(frozen=True)
class LaunchAgentPaths:
    python: Path
    repo: Path
    home: Path


def current_launch_agent_paths() -> LaunchAgentPaths:
    return LaunchAgentPaths(
        python=Path(sys.executable).resolve(),
        repo=Path(__file__).resolve().parents[1],
        home=Path.home(),
    )


def render_launch_agent(paths: LaunchAgentPaths) -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    return (
        template.replace("__PYTHON__", str(paths.python))
        .replace("__REPO__", str(paths.repo))
        .replace("__HOME__", str(paths.home))
    )


def is_enabled() -> bool:
    return DESTINATION_PATH.exists()


def enable() -> None:
    DESTINATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    Path("~/Library/Logs").expanduser().mkdir(parents=True, exist_ok=True)
    DESTINATION_PATH.write_text(
        render_launch_agent(current_launch_agent_paths()),
        encoding="utf-8",
    )
    _launchctl("bootout", check=False)
    _launchctl("bootstrap", check=True)


def disable() -> None:
    _launchctl("bootout", check=False)
    DESTINATION_PATH.unlink(missing_ok=True)


def _launchctl(action: str, *, check: bool) -> None:
    domain = f"gui/{os.getuid()}"
    command = ["launchctl", action, domain]
    if action == "bootstrap":
        command.append(str(DESTINATION_PATH))
    else:
        command.append(LABEL)
    subprocess.run(command, check=check, capture_output=True, text=True)
