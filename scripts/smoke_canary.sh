#!/usr/bin/env bash
# Deterministic canary: requires config mode:live, executor.agent=grok, executor.enabled=true
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CFG="${1:-$ROOT/config.yaml}"
REPO="${2:-mikolaj92/lokay-lite}"
cd "$ROOT"
uv run pytest -q
uv run lokay validate --config "$CFG"
uv run lokay-list-issues --config "$CFG" --repo "$REPO"
echo "smoke ok (list + tests). For full live: lokay-issue-to-pr --live"
