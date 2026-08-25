#!/usr/bin/env bash
# OS caretaker for LaunchAgent ai.mikolaj.lokay-mill.
# Product idle / host-ff / survey live in Fala. This script only leases the
# mill lock, execs lokay-daemon, logs, and records a bootstrap incident if
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
LOKAY_LAUNCHD_LABEL="${LOKAY_LAUNCHD_LABEL:-ai.mikolaj.lokay-mill}"
LOKAY_LAUNCHD_START_INTERVAL=60
LOKAY_LAUNCHD_PLIST="${LOKAY_LAUNCHD_PLIST:-${HOME}/Library/LaunchAgents/${LOKAY_LAUNCHD_LABEL}.plist}"
LOKAY_MILL_LOCK="${LOKAY_MILL_LOCK:-${LOKAY_HOME}/mill.lock}"

bootstrap_incident() {
  if [[ -f "${OUTBOX}" ]] && [[ "$(wc -c < "${OUTBOX}")" -ge 65536 ]]; then
    : > "${OUTBOX}"
  fi
  printf '{"health":"preflight_failed","code":"%s"}\n' "$1" >> "${OUTBOX}"
}

mill_lock_busy() {
  local lock="${LOKAY_MILL_LOCK}"
  [[ -e "${lock}" ]] || return 1
  python3 - "${lock}" <<'PY' 2>/dev/null || return 1
import fcntl, sys
path = sys.argv[1]
try:
    handle = open(path, "a+", encoding="utf-8")
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
except OSError:
    raise SystemExit(0)
raise SystemExit(1)
PY
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
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"
export LOKAY_MODE="${LOKAY_MODE:-live}"
export LOKAY_EXECUTOR_ENABLED="${LOKAY_EXECUTOR_ENABLED:-1}"
export LOKAY_MERGE_ENABLED="${LOKAY_MERGE_ENABLED:-1}"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="${LOG_DIR}/mill-${STAMP}.log"
LATEST="${LOG_DIR}/mill-latest.log"
printf '%s\n' '{"ok":true,"health":"current","reason":"starting"}' | tee "${LOG}" >"${LATEST}"

if mill_lock_busy; then
  printf '%s\n' '{"ok":true,"health":"current","reason":"lock_busy"}' | tee "${LOG}" >"${LATEST}"
  printf '%s\n' '{"ok":true,"health":"current","reason":"lock_busy"}'
  exit 0
fi

set +e
uv run lokay-daemon --config "${CFG}" --max-passes "${LOKAY_MAX_PASSES:-8}" --outbox "${OUTBOX}" >>"${LOG}" 2>&1
MILL_RC=$?
set -e
cp "${LOG}" "${LATEST}" 2>/dev/null || true
if [[ "${MILL_RC}" -ne 0 ]]; then
  bootstrap_incident "daemon_exec"
fi
exit "${MILL_RC}"
