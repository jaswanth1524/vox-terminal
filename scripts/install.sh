#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)

echo "scripts/install.sh is deprecated; running the canonical setup instead."
exec "$ROOT/scripts/bootstrap.sh"
