from __future__ import annotations

import shutil
import sys


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
    print("Grant these to the binary or app that launches Vox Terminal.")
    print(f"Current Python binary: {sys.executable}")
    print("If launched from a terminal, also grant the terminal app itself.")
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
