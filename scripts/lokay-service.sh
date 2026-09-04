#!/usr/bin/env bash
# OS caretaker for LaunchAgent ai.mikolaj.lokay.
# Product idle / host-ff / survey live in Fala. This script only leases the
# lokay lock, execs lokay-daemon, logs, and records a bootstrap incident if
# the process cannot start. Plist 60s + crash KeepAlive is host setup
# (`--install`), not a per-tick rewrite.
set -euo pipefail

HOME="${HOME:-${TMPDIR:-/tmp}/lokay-${UID:-unknown}}"
export HOME
export PATH="${HOME}/.local/bin:${HOME}/.local/share/mise/shims:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"
export LANG="${LANG:-C.UTF-8}"
export TMPDIR="${TMPDIR:-/tmp}"

export LOKAY_ROOT="${LOKAY_ROOT:-${HOME}/Developer/OSS/lokay}"
export FALA_HOME="${FALA_HOME:-${HOME}/Developer/OSS/Fala}"
ROOT="${LOKAY_ROOT}"
export LOKAY_CONFIG="${LOKAY_CONFIG:-${ROOT}/config.yaml}"
CFG="${LOKAY_CONFIG}"
LOKAY_HOME="${HOME}/.lokay"
LOG_DIR="${LOKAY_LOG_DIR:-${LOKAY_HOME}/logs}"
OUTBOX="${LOKAY_HOME}/preflight-bootstrap-incidents.log"
LOKAY_LAUNCHD_LABEL="${LOKAY_LAUNCHD_LABEL:-ai.mikolaj.lokay}"
LOKAY_LAUNCHD_START_INTERVAL=60
LOKAY_LAUNCHD_PLIST="${LOKAY_LAUNCHD_PLIST:-${HOME}/Library/LaunchAgents/${LOKAY_LAUNCHD_LABEL}.plist}"

bootstrap_incident() {
  if [[ -f "${OUTBOX}" ]] && [[ "$(wc -c < "${OUTBOX}")" -ge 65536 ]]; then
    : > "${OUTBOX}"
  fi
  printf '{"health":"preflight_failed","code":"%s"}\n' "$1" >> "${OUTBOX}"
}

write_host_plist() {
  # Host setup only. Missing plist stays missing. Do not invent a job.
  # plutil only — tick path never rewrites the interval.
  local plist="${LOKAY_LAUNCHD_PLIST}"
  [[ -f "${plist}" ]] || return 0
  command -v plutil >/dev/null 2>&1 || return 0
  plutil -replace StartInterval -integer "${LOKAY_LAUNCHD_START_INTERVAL}" "${plist}" >/dev/null 2>&1 || true
  plutil -replace KeepAlive -json '{"SuccessfulExit":false}' "${plist}" >/dev/null 2>&1 || true
}

if [[ "${1:-}" == "--install" ]]; then
  mkdir -p "${LOKAY_HOME}" || exit 70
  write_host_plist || true
  exit 0
fi

mkdir -p "${LOKAY_HOME}" || exit 70
if ! mkdir -p "${LOG_DIR}"; then
  bootstrap_incident "log_directory"
  exit 73
fi
if ! command -v uv >/dev/null 2>&1; then
  bootstrap_incident "uv_unavailable"
  exit 69
fi
if [[ ! -d "${ROOT}" || ! -f "${CFG}" ]]; then
  bootstrap_incident "root_or_config"
  exit 66
fi

cd "${ROOT}"
export LOKAY_ROOT="${ROOT}"
unset LOKAY_PROCESS_HEAD
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"
export LOKAY_MODE="${LOKAY_MODE:-live}"
export LOKAY_EXECUTOR_ENABLED="${LOKAY_EXECUTOR_ENABLED:-1}"
export LOKAY_MERGE_ENABLED="${LOKAY_MERGE_ENABLED:-1}"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="${LOG_DIR}/lokay-${STAMP}.log"
LATEST="${LOG_DIR}/lokay-latest.log"
printf '%s\n' '{"ok":true,"health":"current","reason":"starting"}' | tee "${LOG}" >"${LATEST}"

CEILING="${LOKAY_PASS_CEILING_SECONDS:-180}"
CEILING="${CEILING%.*}"
case "${CEILING}" in
  ''|*[!0-9]*) CEILING=180 ;;
esac
if [[ "${CEILING}" -lt 1 ]]; then
  CEILING=1
fi

write_pass_ceiling_receipt() {
  uv run python - "${CFG}" "${CEILING}" <<'PY' 2>/dev/null || true
from lokay.proc.write_pass_ceiling_receipt import main
import sys
raise SystemExit(main(sys.argv[1:]))
PY
}

stop_lock_owner() {
  # Signal the lock-owning uv/lokay-daemon tree in this session only.
  # Detached issue_to_pr uses start_new_session and must survive.
  local root_pid="$1"
  uv run python - "${root_pid}" <<'PY' 2>/dev/null || true
import os, signal, subprocess, sys, time

root = int(sys.argv[1])
try:
    self_sid = os.getsid(os.getpid())
except OSError:
    raise SystemExit(0)

def children(pid: int) -> list[int]:
    try:
        out = subprocess.run(
            ["pgrep", "-P", str(pid)],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return []
    return [int(line) for line in (out.stdout or "").split() if line.strip().isdigit()]

def walk(pid: int, acc: list[int]) -> None:
    for child in children(pid):
        acc.append(child)
        walk(child, acc)

tree = [root]
walk(root, tree)
same_session = []
for pid in tree:
    try:
        if os.getsid(pid) == self_sid:
            same_session.append(pid)
    except OSError:
        continue

def signal_tree(signum: int) -> None:
    for pid in reversed(same_session):
        try:
            os.kill(pid, signum)
        except OSError:
            pass

signal_tree(signal.SIGTERM)
deadline = time.monotonic() + 5
while time.monotonic() < deadline:
    alive = False
    for pid in same_session:
        try:
            os.kill(pid, 0)
            alive = True
            break
        except OSError:
            continue
    if not alive:
        break
    time.sleep(0.05)
else:
    signal_tree(signal.SIGKILL)
PY
}

set +e
uv run lokay-daemon --config "${CFG}" --max-passes "${LOKAY_MAX_PASSES:-8}" --outbox "${OUTBOX}" >>"${LOG}" 2>&1 &
DAEMON_PID=$!
(
  sleep "${CEILING}"
  if kill -0 "${DAEMON_PID}" 2>/dev/null; then
    printf '%s\n' "${DAEMON_PID}" >"${LOKAY_HOME}/.pass-ceiling.${DAEMON_PID}"
    stop_lock_owner "${DAEMON_PID}"
  fi
) &
WATCHDOG_PID=$!
wait "${DAEMON_PID}"
LOKAY_RC=$?
if kill -0 "${WATCHDOG_PID}" 2>/dev/null; then
  pkill -P "${WATCHDOG_PID}" 2>/dev/null || true
  kill "${WATCHDOG_PID}" 2>/dev/null || true
  wait "${WATCHDOG_PID}" 2>/dev/null || true
fi
CEILING_MARK="${LOKAY_HOME}/.pass-ceiling.${DAEMON_PID}"
if [[ -f "${CEILING_MARK}" ]]; then
  rm -f "${CEILING_MARK}"
  envelope="$(write_pass_ceiling_receipt)"
  if [[ -z "${envelope}" ]]; then
    envelope='{"ok":false,"health":"pass_ceiling","reason":"pass_ceiling"}'
  fi
  printf '%s\n' "${envelope}" | tee -a "${LOG}" >"${LATEST}"
  set -e
  exit 0
fi
set -e
cp "${LOG}" "${LATEST}" 2>/dev/null || true
if [[ "${LOKAY_RC}" -ne 0 ]]; then
  bootstrap_incident "daemon_exec"
fi
exit "${LOKAY_RC}"
