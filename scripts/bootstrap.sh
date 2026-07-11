#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)

if [ "$(uname -s)" != "Darwin" ]; then
  echo "Vox Terminal builds only on macOS." >&2
  exit 1
fi

if [ "$(uname -m)" != "arm64" ]; then
  echo "Vox Terminal requires an Apple-Silicon (arm64) Mac." >&2
  exit 1
fi

MACOS_MAJOR=$(sw_vers -productVersion | cut -d. -f1)
if [ "$MACOS_MAJOR" -lt 13 ]; then
  echo "Vox Terminal requires macOS 13 or newer." >&2
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install it from https://docs.astral.sh/uv/ and rerun make setup." >&2
  exit 1
fi

cd "$ROOT"
uv sync --python 3.11 --frozen --group dev --group build

if ! .venv/bin/python -c "import sounddevice" >/dev/null 2>&1; then
  echo "sounddevice could not load PortAudio. Install it with 'brew install portaudio'." >&2
  exit 1
fi

echo "Vox Terminal development environment is ready."
