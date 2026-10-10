#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$root"
uv run python - <<'PY'
import sys
from lokay.safety import SafetyError, validate_argv

cases = [
    ["git", "push", "--force"],
    ["git", "push", "origin", "main"],
    ["git", "push", "origin", "HEAD:main"],
    ["git", "push", "origin", "HEAD:refs/heads/main"],
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
allowed = ["git", "push", "-u", "origin", "lokay/1-feature"]
try:
    validate_argv(allowed)
except SafetyError as exc:
    sys.exit(f"rejected allowed command: {allowed}: {exc}")
print(f"allowed: {allowed}")
print("safety ok")
PY
