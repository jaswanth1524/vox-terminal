#!/bin/sh
set -eu

cd "$(dirname "$0")/.."

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install it first: https://docs.astral.sh/uv/"
  exit 1
fi

echo "Syncing Python dependencies..."
uv sync --group dev --group build

mkdir -p "$HOME/.config/dictate"
if [ ! -f "$HOME/.config/dictate/config.toml" ]; then
  uv run python - <<'PY'
from pathlib import Path
from dictate.config import as_toml_example

path = Path("~/.config/dictate/config.toml").expanduser()
path.write_text(as_toml_example(), encoding="utf-8")
print(f"Wrote default config: {path}")
PY
fi

echo "Running permission diagnostics..."
if ! uv run python -m dictate.doctor; then
  echo
  echo "One or more permissions are missing. Grant them in System Settings, then run Vox Terminal again."
fi

echo
echo "Developer setup complete."
echo "Build and install the local app: make install"
echo "The app offers to download the Whisper model on first launch."
echo "Run Phase 0: uv run python scripts/phase0_spike.py"
echo "Run Vox Terminal menu bar: uv run python -m dictate"
echo "Run foreground debug mode: uv run python -m dictate --no-menubar"
echo "Run ASR benchmark: uv run python scripts/benchmark_parakeet.py --audio tests/fixtures/hello_world.wav"
echo "Start at Login is available from the installed app's menu."
