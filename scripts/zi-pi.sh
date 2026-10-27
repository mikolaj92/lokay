#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec uv run --project "$root" python -m lokay.effects.launcher "$@"
