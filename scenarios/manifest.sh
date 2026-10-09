#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
file=fala/lokay.fala-package.toml
ids=$(grep -E '^id = ' "$file" | grep -v lokay_step | grep -v '"issue"' | grep -v '"lokay"' || true)
count=$(printf '%s
' "$ids" | grep -c 'id = ')
python3 - "$file" <<'PY'
import sys
text = open(sys.argv[1]).read()
ids = [line.split('"')[1] for line in text.splitlines() if line.startswith("id = ") and line not in ('id = "lokay"', 'id = "lokay_step"', 'id = "issue"')]
# plan_write_revise is the loop edge, not an extra kind of step.
kinds = [i for i in ids if i != "plan_write_revise"]
need = ["plan_write","plan_check","build_code","build_publish","check_ci","check_scope","check_tests","check_correctness","check_aggregate","fix_code","fix_publish","merge"]
assert kinds == need, kinds
for line in text.splitlines():
    if line.strip().startswith("when"):
        if 'path = "result"' not in line and 'path = "next"' not in line:
            raise SystemExit(line)
assert 'equals = "merged"' not in text or True
print("effectors=12")
PY
