from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
    if _is_app_bundle():
        return int(_main_app_service().status()) == 1
    return DESTINATION_PATH.exists()


def enable() -> None:
    if _is_app_bundle():
        _call_service(_main_app_service(), "registerAndReturnError_")
        return
    raise RuntimeError(
        "Start at Login is available after installing Vox Terminal.app. "
        "Run `make install`, then launch the app from ~/Applications."
    )


def enable_legacy() -> None:
    """Retained for tests and migration from pre-app installations."""

    DESTINATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    Path("~/Library/Logs").expanduser().mkdir(parents=True, exist_ok=True)
    DESTINATION_PATH.write_text(
        render_launch_agent(current_launch_agent_paths()),
        encoding="utf-8",
    )
    _launchctl("bootout", check=False)
    _launchctl("bootstrap", check=True)


def disable() -> None:
    if _is_app_bundle():
        _call_service(_main_app_service(), "unregisterAndReturnError_")
        return
    _launchctl("bootout", check=False)
    DESTINATION_PATH.unlink(missing_ok=True)


def migrate_legacy() -> bool:
    """Remove the old repo-bound LaunchAgent and preserve login startup."""

    if not _is_app_bundle() or not DESTINATION_PATH.exists():
        return False
    _launchctl("bootout", check=False)
    DESTINATION_PATH.unlink(missing_ok=True)
    _call_service(_main_app_service(), "registerAndReturnError_")
    return True


def _is_app_bundle() -> bool:
    try:
        from Foundation import NSBundle

        return str(NSBundle.mainBundle().bundlePath()).endswith(".app")
    except Exception:
        return False


def _main_app_service() -> Any:
    import objc

    objc.loadBundle(
        "ServiceManagement",
        globals(),
        bundle_path="/System/Library/Frameworks/ServiceManagement.framework",
    )
    service_class = objc.lookUpClass("SMAppService")
    return service_class.mainAppService()


def _call_service(service: Any, method_name: str) -> None:
    result = getattr(service, method_name)(None)
    if isinstance(result, tuple):
        succeeded, error = result
    else:
        succeeded, error = bool(result), None
    if not succeeded:
        raise RuntimeError(str(error or "macOS rejected the login item request"))


def _launchctl(action: str, *, check: bool) -> None:
    domain = f"gui/{os.getuid()}"
    command = ["launchctl", action, domain]
    if action == "bootstrap":
        command.append(str(DESTINATION_PATH))
    else:
        command.append(LABEL)
    subprocess.run(command, check=check, capture_output=True, text=True)
