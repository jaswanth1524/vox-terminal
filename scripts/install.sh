#!/bin/sh
set -eu

cd "$(dirname "$0")/.."

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install it first: https://docs.astral.sh/uv/"
  exit 1
fi

echo "Syncing Python dependencies..."
uv sync

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

MODEL="$(uv run python - <<'PY'
from dictate.config import load_config
print(load_config().model)
PY
)"

LANGUAGE="$(uv run python - <<'PY'
from dictate.config import load_config
print(load_config().language)
PY
)"

echo "Downloading and warming model: $MODEL"
uv run python -m dictate.transcriber --download-model --model "$MODEL" --language "$LANGUAGE"

echo "Running permission diagnostics..."
if ! uv run python -m dictate.doctor; then
  echo
  echo "One or more permissions are missing. Grant them in System Settings, then run Dictate again."
fi

echo
echo "Install complete."
echo "Run Phase 0: uv run python scripts/phase0_spike.py"
echo "Run Dictate menu bar: uv run python -m dictate"
echo "Run foreground debug mode: uv run python -m dictate --no-menubar"
echo "Start at Login can be toggled from the Dictate menu bar item."
