#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
APP="$ROOT/dist/Vox Terminal.app"
VERSION=$("$ROOT/.venv/bin/python" "$ROOT/scripts/project_version.py")
OUTPUT_DIR=${RELEASE_OUTPUT_DIR:-"$ROOT/dist/release"}
BASE="Vox-Terminal-$VERSION-macOS-arm64"
ARCHIVE="$OUTPUT_DIR/$BASE.zip"
CHECKSUM="$OUTPUT_DIR/$BASE.sha256"
DEPENDENCIES="$OUTPUT_DIR/$BASE-dependencies.txt"
SBOM="$OUTPUT_DIR/$BASE.spdx.json"

if [ ! -d "$APP" ]; then
  echo "App bundle not found. Run 'make app' first." >&2
  exit 1
fi

mkdir -p "$OUTPUT_DIR"
# Prevent a previous version from being uploaded by the release workflow's wildcard.
find "$OUTPUT_DIR" -mindepth 1 -maxdepth 1 -type f \
  -name 'Vox-Terminal-*-macOS-arm64*' -delete
ditto -c -k --sequesterRsrc --keepParent "$APP" "$ARCHIVE"

ARCHIVE_HASH=$(shasum -a 256 "$ARCHIVE" | awk '{print $1}')
printf '%s  %s\n' "$ARCHIVE_HASH" "$(basename "$ARCHIVE")" > "$CHECKSUM"

cd "$ROOT"
uv export --frozen --no-dev --no-emit-project --no-hashes \
  --format requirements.txt --output-file "$DEPENDENCIES" >/dev/null
"$ROOT/.venv/bin/python" "$ROOT/scripts/generate_sbom.py" \
  --app "$APP" \
  --analysis "$ROOT/build/VoxTerminal/PYZ-00.toc" \
  --output "$SBOM"

echo "Release artifacts:"
echo "  $ARCHIVE"
echo "  $CHECKSUM"
echo "  $DEPENDENCIES"
echo "  $SBOM"
