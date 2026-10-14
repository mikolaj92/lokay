#!/usr/bin/env bash
# Caretaker for LaunchAgent ai.mikolaj.lokay2.
main() {
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
export LOKAY2_DECISION_API="${LOKAY2_DECISION_API-mini}"
export LOKAY2_DECISION_BASE_URL="${LOKAY2_DECISION_BASE_URL-http://192.168.1.52:8005}"
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
if [[ "${1:-}" == "--monitor" ]]; then
  exec "$ROOT/.venv/bin/lokay" monitor >>"$LOG" 2>&1
fi
while true; do
  if [[ -f "$LOG" ]] && (( $(wc -c <"$LOG") >= 10485760 )); then
    mv -f "$LOG" "$LOG.1" || exit 73
  fi
  update=$(bash "$ROOT/scripts/self_update.sh" 2>>"$LOG")
  update_rc=$?
  printf '%s\n' "$update" >>"$LOG"
  if (( update_rc == 0 )); then
    export LOKAY_VERSION="$(printf '%s' "$update" | "$ROOT/.venv/bin/python" -c 'import json,sys; print(json.load(sys.stdin)["head"])')"
    if [[ "$update" == *'"result":"updated"'* ]]; then
      exec bash "$ROOT/scripts/lokay-service.sh" "$@"
    fi
  fi
  date -u '+%Y-%m-%dT%H:%M:%SZ' >>"$LOG"
  if [[ "${LOKAY_DARKFACTORY_CANARY:-0}" == "1" ]]; then
    if [[ "${LOKAY2_REPO:-}" != "mikolaj92/lokay-sandbox" ]]; then
      printf 'canary requires sandbox-only LOKAY2_REPO\n' >>"$LOG"
      exit 64
    fi
    bash "$ROOT/scripts/darkfactory-canary.sh" >>"$LOG" 2>&1 || {
      [[ "${1:-}" == "--once" ]] && exit 1
      sleep "$LOKAY_TICK_SECONDS"
      continue
    }
  fi
  "$ROOT/.venv/bin/lokay" start </dev/null >>"$LOG" 2>&1
  rc=$?
  [[ "${1:-}" == "--once" ]] && exit "$rc"
  sleep "$LOKAY_TICK_SECONDS"
done
}
main "$@"
