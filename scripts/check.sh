#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
if grep -rnE '^(<<<<<<< |>>>>>>> |=======$)' src/ prompts/ sandbox/ scripts/; then
    exit 1
else
    [ "$?" -eq 1 ]
fi
sandbox=$(mktemp -d "${TMPDIR:-/tmp}/lokay-check.XXXXXX")
trap 'rm -rf "$sandbox"' EXIT HUP INT TERM
export UV_CACHE_DIR="$sandbox/cache"
export UV_PROJECT_ENVIRONMENT="$PWD/.venv"
export UV_LOCKED=1
env -u UV_NO_SYNC -u UV_OFFLINE uv sync --locked --all-extras
.venv/bin/python -m compileall -q src
.venv/bin/python -I - <<'PY'
from pathlib import Path
import importlib
import pkgutil

import lokay
import yaml

expected = (Path.cwd() / 'src/lokay').resolve()
if lokay.__file__ is None or Path(lokay.__file__).resolve().parent != expected:
    raise SystemExit(f'wrong lokay location: {lokay.__file__}; expected {expected}')
def import_failed(name):
    raise ImportError(f'cannot import {name}')

for module in pkgutil.walk_packages(lokay.__path__, lokay.__name__ + '.', onerror=import_failed):
    importlib.import_module(module.name)
PY
mkdir -p "$sandbox/home" "$sandbox/tmp" "$sandbox/cache" "$sandbox/bin"
printf '%s\n' '#!/bin/sh' 'echo "unexpected external gh (blocked by local check)" >&2' 'exit 1' > "$sandbox/bin/gh"
chmod +x "$sandbox/bin/gh"
export HOME="$sandbox/home" TMPDIR="$sandbox/tmp" UV_CACHE_DIR="$sandbox/cache"
export UV_NO_SYNC=1 UV_PYTHON_DOWNLOADS=never UV_OFFLINE=1 PATH="$sandbox/bin:$PATH"
.venv/bin/python -m lokay.gh_boundary
uv run lokay replay fixtures/replay/
uv run lokay replay fixtures/ticks/
