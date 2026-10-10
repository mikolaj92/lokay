#!/usr/bin/env bash
# Caretaker for LaunchAgent ai.mikolaj.lokay.
set -uo pipefail

export HOME="${HOME:-${TMPDIR:-/tmp}/lokay-${UID:-unknown}}"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:${PATH:-/usr/bin:/bin}"
if [[ -f "$HOME/.config/lokay/env" ]]; then
  set -a
  source "$HOME/.config/lokay/env"
  set +a
fi

export LOKAY_ROOT="${LOKAY_ROOT-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)}"
export LOKAY2_PROVIDER="${LOKAY2_PROVIDER-omniroute}"
export LOKAY2_MODEL="${LOKAY2_MODEL-pi}"
export LOKAY2_DECISION_API="${LOKAY2_DECISION_API-tensorfold}"
export LOKAY2_DECISION_BASE_URL="${LOKAY2_DECISION_BASE_URL-http://192.168.1.60:8888}"
export LOKAY2_DECISION_MODEL="${LOKAY2_DECISION_MODEL-GLM-5.3-Flash-EXL3}"
export LOKAY_TICK_SECONDS="${LOKAY_TICK_SECONDS-60}"
ROOT="$LOKAY_ROOT"
if [[ -z "${GH_TOKEN:-}" ]]; then
  export GH_TOKEN="$(gh auth token 2>/dev/null || true)"
fi
if [[ ! -x "$ROOT/.venv/bin/lokay" ]]; then
  printf 'lokay executable unavailable: %s/.venv/bin/lokay\n' "$ROOT" >&2
  exit 69
fi

LOG="$HOME/.lokay/logs/lokay.log"
mkdir -p "$(dirname -- "$LOG")" || exit 73
while true; do
  {
    date -u '+%Y-%m-%dT%H:%M:%SZ'
    "$ROOT/.venv/bin/lokay" start </dev/null
  } >>"$LOG" 2>&1
  rc=$?
  [[ "${1:-}" == "--once" ]] && exit "$rc"
  sleep "$LOKAY_TICK_SECONDS"
done
