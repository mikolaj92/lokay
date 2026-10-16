#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
validation_root=${VALIDATION_DIR:-$PWD}
mkdir -p "$validation_root"
validation_root=$(CDPATH= cd -- "$validation_root" && pwd)
export UV_PROJECT_ENVIRONMENT="$validation_root/.venv"
env -u UV_NO_SYNC -u UV_OFFLINE uv sync --frozen
"$UV_PROJECT_ENVIRONMENT/bin/python" -I - <<'PY'
from pathlib import Path

import lokay
import yaml

expected = (Path.cwd() / 'src/lokay').resolve()
if lokay.__file__ is None or Path(lokay.__file__).resolve().parent != expected:
    raise SystemExit(f'wrong lokay location: {lokay.__file__}; expected {expected}')
PY
mkdir -p "$validation_root/.uv"
sandbox=$(mktemp -d "$validation_root/.uv/check.XXXXXX")
trap 'rm -rf "$sandbox"' EXIT HUP INT TERM
mkdir -p "$sandbox/home" "$sandbox/tmp" "$sandbox/cache" "$sandbox/bin"
printf '%s\n' '#!/bin/sh' 'echo "unexpected external gh (blocked by local check)" >&2' 'exit 1' > "$sandbox/bin/gh"
chmod +x "$sandbox/bin/gh"
export HOME="$sandbox/home" TMPDIR="$sandbox/tmp" UV_CACHE_DIR="$sandbox/cache"
export UV_NO_SYNC=1 UV_PYTHON_DOWNLOADS=never UV_OFFLINE=1 PATH="$sandbox/bin:$PATH"
uv run lokay replay fixtures/replay/
