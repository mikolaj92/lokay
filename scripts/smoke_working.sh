#!/usr/bin/env bash
# WORKING smoke: tests + graphs + status. Does not mutate GitHub.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CFG="${1:-$ROOT/config.yaml}"
cd "$ROOT"

uv run pytest -q
uv run lokay validate --config "$CFG"
uv run lokay path --describe | uv run python -c "
import json,sys
d=json.load(sys.stdin)
ids=sorted(p['id'] for p in d.get('paths') or [])
need={'issue_to_pr','issue_triage','pr_repair','pr_triage'}
missing=need-set(ids)
assert not missing, f'missing graphs: {missing}'
print('graphs ok', ids)
"
uv run lokay status --config "$CFG" || true
echo "smoke_working ok (tests+graphs+status). Live lokay: see docs/WORKING.md env overrides."
