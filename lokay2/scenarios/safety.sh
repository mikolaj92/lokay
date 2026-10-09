#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$root"
uv run python - <<'PY'
import sys
from lokay2.safety import SafetyError, validate_argv

cases = [
    ["git", "push", "--force"],
    ["gh", "pr", "merge", "--admin"],
    ["gh", "repo", "delete", "mikolaj92/lokay"],
    ["rm", "-rf", "/"],
]
for argv in cases:
    try:
        validate_argv(argv)
    except SafetyError as exc:
        print(f"rejected: {exc}")
        continue
    sys.exit(f"allowed: {argv}")
print("safety ok")
PY
