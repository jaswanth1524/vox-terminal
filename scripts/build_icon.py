from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "app-icon.svg"
BUILD = ROOT / "build"
MASTER = BUILD / "VoxTerminal-1024.png"
OUTPUT = BUILD / "VoxTerminal.icns"


def main() -> int:
    renderer = shutil.which("rsvg-convert")
    if renderer is None:
        raise SystemExit(
            "rsvg-convert is required to build the app icon (brew install librsvg)."
        )
    BUILD.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [renderer, "-w", "1024", "-h", "1024", str(SOURCE), "-o", str(MASTER)],
        check=True,
    )
    try:
        with Image.open(MASTER) as image:
            image.save(
                OUTPUT,
                format="ICNS",
                sizes=[
                    (16, 16),
                    (32, 32),
                    (64, 64),
                    (128, 128),
                    (256, 256),
                    (512, 512),
                    (1024, 1024),
                ],
            )
    finally:
        MASTER.unlink(missing_ok=True)
    print(f"Built {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
