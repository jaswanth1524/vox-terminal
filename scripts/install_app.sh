#!/bin/sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
SOURCE="$ROOT/dist/Vox Terminal.app"
DESTINATION="$HOME/Applications/Vox Terminal.app"

if [ ! -d "$SOURCE" ]; then
  echo "App bundle not found. Run 'make app' first."
  exit 1
fi

mkdir -p "$HOME/Applications"
rm -rf "$DESTINATION"
ditto "$SOURCE" "$DESTINATION"
codesign --force --deep --sign - "$DESTINATION"

echo "Installed in your personal Applications folder: $DESTINATION"
echo "Reveal it in Finder: open -R '$DESTINATION'"
echo "Launch it from Finder or run: open '$DESTINATION'"
