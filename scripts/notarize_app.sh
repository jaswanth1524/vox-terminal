#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
APP=${1:-"$ROOT/dist/Vox Terminal.app"}

: "${APPLE_ID:?APPLE_ID is required for notarization}"
: "${APPLE_TEAM_ID:?APPLE_TEAM_ID is required for notarization}"
: "${APPLE_APP_SPECIFIC_PASSWORD:?APPLE_APP_SPECIFIC_PASSWORD is required for notarization}"

if [ ! -d "$APP" ]; then
  echo "App bundle not found: $APP" >&2
  exit 1
fi

WORK_DIR=$(mktemp -d "${TMPDIR:-/tmp}/vox-terminal-notary.XXXXXX")
UPLOAD="$WORK_DIR/Vox-Terminal.zip"
trap 'rm -rf "$WORK_DIR"' EXIT HUP INT TERM

ditto -c -k --sequesterRsrc --keepParent "$APP" "$UPLOAD"
xcrun notarytool submit "$UPLOAD" \
  --apple-id "$APPLE_ID" \
  --team-id "$APPLE_TEAM_ID" \
  --password "$APPLE_APP_SPECIFIC_PASSWORD" \
  --wait
xcrun stapler staple "$APP"
xcrun stapler validate "$APP"
spctl --assess --type execute --verbose=2 "$APP"

echo "Notarization and stapling completed."
