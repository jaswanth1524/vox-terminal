from __future__ import annotations

import shutil
import sys
from pathlib import Path


def permission_target_description(
    *,
    executable: str | None = None,
    frozen: bool | None = None,
) -> str:
    executable_path = Path(executable or sys.executable)
    is_frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    if is_frozen and len(executable_path.parents) >= 3:
        app_path = executable_path.parents[2]
        if app_path.suffix == ".app":
            return str(app_path)
    return "the launching terminal app and virtual-environment Python"


def check_microphone() -> tuple[bool, str]:
    try:
        import sounddevice as sd

        devices = sd.query_devices()
    except Exception as exc:
        return False, f"Microphone check failed: {exc}"
    if not devices:
        return False, "No audio devices reported by PortAudio."
    return True, "PortAudio can enumerate audio devices."


def check_accessibility() -> tuple[bool, str]:
    try:
        from ApplicationServices import AXIsProcessTrusted
    except Exception as exc:
        return False, f"Accessibility check unavailable: {exc}"
    trusted = bool(AXIsProcessTrusted())
    if trusted:
        return True, "Accessibility permission appears to be granted."
    return False, "Accessibility permission is not granted for this host process."


def print_permission_instructions() -> None:
    print()
    print("macOS permissions required:")
    print("1. System Settings -> Privacy & Security -> Microphone")
    print("2. System Settings -> Privacy & Security -> Accessibility")
    print("3. System Settings -> Privacy & Security -> Input Monitoring")
    print()
    print(f"Grant these to: {permission_target_description()}")
    print(f"Current Python binary: {sys.executable}")
    print("Input Monitoring cannot be verified noninteractively; Vox Terminal warns at startup")
    print("if the global keyboard listener receives no events.")


def main() -> int:
    print(f"Python: {sys.executable}")
    print(f"pbcopy: {shutil.which('pbcopy') or 'missing'}")
    print(f"pbpaste: {shutil.which('pbpaste') or 'missing'}")
    print(f"afplay: {shutil.which('afplay') or 'missing'}")

    checks = [check_microphone(), check_accessibility()]
    ok = True
    for passed, message in checks:
        ok = ok and passed
        status = "OK" if passed else "WARN"
        print(f"{status}: {message}")

    print_permission_instructions()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
