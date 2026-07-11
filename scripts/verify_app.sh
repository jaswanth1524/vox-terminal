#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
APP=${1:-"$ROOT/dist/Vox Terminal.app"}
MAX_BUNDLE_MB=${MAX_BUNDLE_MB:-300}
EXECUTABLE="$APP/Contents/MacOS/Vox Terminal"

if [ ! -x "$EXECUTABLE" ]; then
  echo "App executable not found: $EXECUTABLE" >&2
  exit 1
fi

ARCHS=$(lipo -archs "$EXECUTABLE")
if [ "$ARCHS" != "arm64" ]; then
  echo "Expected an arm64-only executable, found: $ARCHS" >&2
  exit 1
fi

PROJECT_VERSION=$("$ROOT/.venv/bin/python" "$ROOT/scripts/project_version.py")
BUNDLE_VERSION=$(plutil -extract CFBundleShortVersionString raw "$APP/Contents/Info.plist")
if [ "$PROJECT_VERSION" != "$BUNDLE_VERSION" ]; then
  echo "Version mismatch: pyproject=$PROJECT_VERSION bundle=$BUNDLE_VERSION" >&2
  exit 1
fi

codesign --verify --deep --strict --verbose=1 "$APP"
"$EXECUTABLE" --self-test

BUNDLE_KB=$(du -sk "$APP" | awk '{print $1}')
MAX_BUNDLE_KB=$((MAX_BUNDLE_MB * 1024))
if [ "$BUNDLE_KB" -gt "$MAX_BUNDLE_KB" ]; then
  echo "Bundle is $((BUNDLE_KB / 1024)) MB; limit is $MAX_BUNDLE_MB MB." >&2
  exit 1
fi

for package in librosa llvmlite numba scipy silero_vad sklearn torch torchaudio torchgen; do
  if find "$APP/Contents" -type d -name "$package" -print -quit | grep -q .; then
    echo "Prohibited heavyweight package found in bundle: $package" >&2
    exit 1
  fi
done

if [ "${REQUIRE_GATEKEEPER:-0}" = "1" ]; then
  xcrun stapler validate "$APP"
  spctl --assess --type execute --verbose=2 "$APP"
fi

echo "Release checks passed: version $PROJECT_VERSION, arm64, $((BUNDLE_KB / 1024)) MB."
