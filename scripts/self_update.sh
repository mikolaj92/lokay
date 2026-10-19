#!/usr/bin/env bash
set -euo pipefail

result=failed
head=""
report() {
  printf '{"result":"%s","head":"%s"}\n' "$result" "$head"
}
trap report EXIT

LOKAY_ROOT="${LOKAY_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)}"
cd -- "$LOKAY_ROOT"
head=$(git rev-parse HEAD)
status=$(git status --porcelain)
branch=$(git symbolic-ref --quiet --short HEAD || true)
if [[ -n "$status" || "$branch" != main ]]; then
  result=dirty
  exit 0
fi

before="$head"
git fetch origin main >&2
git merge --ff-only origin/main >&2
head=$(git rev-parse HEAD)
if [[ "$head" != "$before" ]]; then
  if command -v uv >/dev/null 2>&1; then
    export UV_CACHE_DIR="${UV_CACHE_DIR:-$HOME/.lokay/uv-cache}"
    uv sync >&2
  fi
  result=updated
else
  result=current
fi
