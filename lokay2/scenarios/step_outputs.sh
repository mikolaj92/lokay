#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$root"
uv run python - <<'PY'
import json
import sys

def accept(payload):
    if set(payload) != {"result", "artifact"}:
        return False
    if payload["result"] not in ("done", "failed"):
        return False
    if not isinstance(payload["artifact"], str):
        return False
    sys.stdout.write(json.dumps(payload, separators=(",", ":")) + "\n")
    return True

good = {"result": "done", "artifact": "runs/1/plan.md"}
bad = {"result": "maybe", "artifact": "runs/1/plan.md"}
if not accept(good):
    sys.exit("good payload rejected")
sys.stdout = open("/dev/null", "w")
if accept(bad):
    sys.stderr.write("bad payload accepted\n")
    raise SystemExit(1)
sys.stderr.write("step outputs ok\n")
PY
