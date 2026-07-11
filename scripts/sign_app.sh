#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
APP=${1:-"$ROOT/dist/Vox Terminal.app"}
IDENTITY=${CODESIGN_IDENTITY:--}

if [ ! -d "$APP" ]; then
  echo "App bundle not found: $APP" >&2
  exit 1
fi

if [ "$IDENTITY" = "-" ]; then
  codesign --force --deep --sign - "$APP"
  echo "Applied an ad-hoc signature."
else
  if ! security find-identity -v -p codesigning | grep -F "$IDENTITY" >/dev/null; then
    echo "Code-signing identity is unavailable: $IDENTITY" >&2
    exit 1
  fi
  codesign --force --deep --options runtime --timestamp --sign "$IDENTITY" "$APP"
  echo "Applied Developer ID signature: $IDENTITY"
fi

codesign --verify --deep --strict --verbose=1 "$APP"
