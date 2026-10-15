#!/usr/bin/env bash
# Caretaker for LaunchAgent ai.mikolaj.lokay2.
main() {
set -uo pipefail

worker_index="${LOKAY2_WORKER-}"
export HOME="${HOME:-${TMPDIR:-/tmp}/lokay-${UID:-unknown}}"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:${PATH:-/usr/bin:/bin}"
if [[ -f "$HOME/.config/lokay/env" ]]; then
  set -a
  source "$HOME/.config/lokay/env"
  set +a
fi
if [[ -n "$worker_index" ]]; then
  export LOKAY2_WORKER="$worker_index"
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
export LOKAY2_WORKERS="${LOKAY2_WORKERS-2}"
case "$LOKAY2_WORKERS" in
  1|2|3) ;;
  *) printf 'LOKAY2_WORKERS must be 1, 2 or 3\n' >&2; exit 64 ;;
esac
set -m
if [[ -z "${LOKAY2_WORKER+x}" ]]; then
  workers=()
  stop_workers() {
    trap '' TERM INT
    for pid in "${workers[@]}"; do kill -s "$1" "$pid" 2>/dev/null || true; done
    for pid in "${workers[@]}"; do wait "$pid" || true; done
    exit "$2"
  }
  trap 'stop_workers TERM 143' TERM
  trap 'stop_workers INT 130' INT
  for ((worker=0; worker<LOKAY2_WORKERS; worker++)); do
    LOKAY2_WORKER="$worker" bash "$ROOT/scripts/lokay-service.sh" "$@" &
    workers+=("$!")
  done
  rc=0
  for pid in "${workers[@]}"; do wait "$pid" || rc=1; done
  exit "$rc"
fi
case "$LOKAY2_WORKER" in
  0|1|2) (( LOKAY2_WORKER < LOKAY2_WORKERS )) || exit 64 ;;
  *) exit 64 ;;
esac
export LOKAY2_WORKER
active=""
update_file=""
stop_worker() {
  trap '' TERM INT
  if [[ -n "$active" ]]; then
    kill -s "$1" -- "-$active" 2>/dev/null || true
    wait "$active" || true
  fi
  [[ -z "$update_file" ]] || rm -f "$update_file"
  exit "$2"
}
trap 'stop_worker TERM 143' TERM
trap 'stop_worker INT 130' INT
run_child() {
  "$@" &
  active=$!
  wait "$active"
  local status=$?
  active=""
  return "$status"
}
while true; do
  if [[ "$LOKAY2_WORKER" == "0" ]]; then
  if [[ -f "$LOG" ]] && (( $(wc -c <"$LOG") >= 10485760 )); then
    mv -f "$LOG" "$LOG.1" || exit 73
  fi
  update_file=$(mktemp) || exit 73
  run_child bash "$ROOT/scripts/self_update.sh" >"$update_file" 2>>"$LOG"
  update_rc=$?
  update=$(<"$update_file")
  rm -f "$update_file"
  update_file=""
  printf '%s\n' "$update" >>"$LOG"
  if (( update_rc == 0 )); then
    export LOKAY_VERSION="$(printf '%s' "$update" | "$ROOT/.venv/bin/python" -c 'import json,sys; print(json.load(sys.stdin)["head"])')"
    if [[ "$update" == *'"result":"updated"'* ]]; then
      exec bash "$ROOT/scripts/lokay-service.sh" "$@"
    fi
  fi
  fi
  date -u '+%Y-%m-%dT%H:%M:%SZ' >>"$LOG"
  if [[ "${LOKAY_DARKFACTORY_CANARY:-0}" == "1" ]]; then
    if [[ "${LOKAY2_REPO:-}" != "mikolaj92/lokay-sandbox" ]]; then
      printf 'canary requires sandbox-only LOKAY2_REPO\n' >>"$LOG"
      exit 64
    fi
    run_child bash "$ROOT/scripts/darkfactory-canary.sh" >>"$LOG" 2>&1 || {
      [[ "${1:-}" == "--once" ]] && exit 1
      run_child sleep "$LOKAY_TICK_SECONDS"
      continue
    }
  fi
  run_child "$ROOT/.venv/bin/lokay" start </dev/null >>"$LOG" 2>&1
  rc=$?
  [[ "${1:-}" == "--once" ]] && exit "$rc"
  run_child sleep "$LOKAY_TICK_SECONDS"
done
}
main "$@"
