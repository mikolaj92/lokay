#!/usr/bin/env bash
# Continuous Lokay mill — one pass, invoked by launchd.
# Scope: repos.mikolaj92.yaml (all managed source repos).
# Host LaunchAgent StartInterval is 60s (not 600). Plist stays on the host.
set -euo pipefail

# launchd should provide HOME; retain a per-uid bounded fallback when it does not.
HOME="${HOME:-${TMPDIR:-/tmp}/lokay-${UID:-unknown}}"
export HOME
export PATH="${HOME}/.local/bin:${HOME}/.local/share/mise/shims:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"
export LANG="${LANG:-C.UTF-8}"
export TMPDIR="${TMPDIR:-/tmp}"

ROOT="${LOKAY_ROOT:-${HOME}/Developer/OSS/lokay}"
CFG="${LOKAY_CONFIG:-${ROOT}/config.yaml}"
LOKAY_HOME="${HOME}/.lokay"
LOG_DIR="${LOKAY_LOG_DIR:-${LOKAY_HOME}/logs}"
OUTBOX="${LOKAY_HOME}/preflight-bootstrap-incidents.log"
LOKAY_LAUNCHD_LABEL="${LOKAY_LAUNCHD_LABEL:-ai.mikolaj.lokay-mill}"
# Fail-closed operator interval: 60s heartbeat, never the old 600s tick.
LOKAY_LAUNCHD_START_INTERVAL=60
LOKAY_LAUNCHD_PLIST="${LOKAY_LAUNCHD_PLIST:-${HOME}/Library/LaunchAgents/${LOKAY_LAUNCHD_LABEL}.plist}"
LOKAY_MILL_LOCK="${LOKAY_MILL_LOCK:-${LOKAY_HOME}/mill.lock}"

_python() {
  if command -v python3 >/dev/null 2>&1; then
    python3 "$@"
  elif [[ -x /usr/bin/python3 ]]; then
    /usr/bin/python3 "$@"
  else
    return 127
  fi
}

bootstrap_incident() {
  # Bound bootstrap evidence even when Python/package/config cannot start.
  if [[ -f "${OUTBOX}" ]] && [[ "$(wc -c < "${OUTBOX}")" -ge 65536 ]]; then
    : > "${OUTBOX}"
  fi
  printf '{"health":"preflight_failed","code":"%s"}\n' "$1" >> "${OUTBOX}"
}

write_host_plist_interval() {
  # Plist is host-only. Write 60s; do not invent a LaunchAgent from the repo.
  local plist="$1"
  local want="$2"
  [[ -f "${plist}" ]] || return 0
  _python - "${plist}" "${want}" <<'PY'
import plistlib, sys

path, want = sys.argv[1], int(sys.argv[2])
with open(path, "rb") as handle:
    data = plistlib.load(handle)
if data.get("StartInterval") == want:
    raise SystemExit(0)
data["StartInterval"] = want
with open(path, "wb") as handle:
    plistlib.dump(data, handle, fmt=plistlib.FMT_XML)
PY
}

mill_lock_busy() {
  # Singleton lock stays: a parallel tick must not start a second mill,
  # and a busy lock means the caretaker must not reload launchd.
  local lock="${LOKAY_MILL_LOCK}"
  [[ -e "${lock}" ]] || return 1
  _python - "${lock}" <<'PY'
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

loaded_start_interval() {
  local label="$1"
  local uid
  uid="$(id -u)"
  command -v launchctl >/dev/null 2>&1 || return 0
  launchctl print "user/${uid}/${label}" 2>/dev/null | awk '/run interval/ {print $4; exit}'
}

reload_launchagent() {
  local plist="$1"
  local label="$2"
  local uid domain
  uid="$(id -u)"
  domain="user/${uid}"
  launchctl bootout "${domain}/${label}" >/dev/null 2>&1 || true
  launchctl bootstrap "${domain}" "${plist}" >/dev/null 2>&1 || true
}

caretaker_write_interval() {
  local plist="${LOKAY_LAUNCHD_PLIST}"
  local want="${LOKAY_LAUNCHD_START_INTERVAL}"
  [[ -f "${plist}" ]] || return 0
  write_host_plist_interval "${plist}" "${want}" || true
}

caretaker_reload_if_idle() {
  # Load the host plist only after idle. Never launchctl while mill.lock
  # is held (lokay is still in a cycle).
  local plist="${LOKAY_LAUNCHD_PLIST}"
  local label="${LOKAY_LAUNCHD_LABEL}"
  local want="${LOKAY_LAUNCHD_START_INTERVAL}"
  local loaded=""
  [[ -f "${plist}" ]] || return 0
  command -v launchctl >/dev/null 2>&1 || return 0
  loaded="$(loaded_start_interval "${label}")"
  if [[ "${loaded}" == "${want}" ]]; then
    return 0
  fi
  if mill_lock_busy; then
    return 0
  fi
  reload_launchagent "${plist}" "${label}"
}

if [[ "${1:-}" == "--install" ]]; then
  mkdir -p "${LOKAY_HOME}" || exit 70
  caretaker_write_interval
  caretaker_reload_if_idle
  exit 0
fi

# Bootstrap precedes uv/package/config/log dependencies and persists bounded failures.
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

# Tick starts on current origin/main or fail-closed (do not mill on stale host code).
if ! uv run lokay-host-ff --config "${CFG}" --live --checkout "${ROOT}"; then
  bootstrap_incident "host_behind"
  exit 78
fi

# Live factory (override with env in the plist if needed). This LaunchAgent
# runs the PR mill only; collector patches own their post-merge durable
# background startup. Never use this loop to populate collector data or wait.
export LOKAY_MODE="${LOKAY_MODE:-live}"
export LOKAY_EXECUTOR_ENABLED="${LOKAY_EXECUTOR_ENABLED:-1}"
export LOKAY_MERGE_ENABLED="${LOKAY_MERGE_ENABLED:-1}"
export LOKAY_REQUIRE_CHECKS="${LOKAY_REQUIRE_CHECKS:-1}"

if [[ -d "${HOME}/Developer/OSS/Fala/mojo/fala" ]]; then
  export FALA_HOME="${FALA_HOME:-${HOME}/Developer/OSS/Fala}"
fi

# Keep the on-disk host interval at 60s. Do not launchctl here — this process
# is the live cycle. Caretaker (--install) loads after idle when the lock is free.
caretaker_write_interval

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="${LOG_DIR}/mill-${STAMP}.log"
LATEST="${LOG_DIR}/mill-latest.log"

# Refresh the preflight carrier before starting: uv otherwise preserves stale
# editable installs of Lokay or Fala after either checkout was repaired.
# One Python process owns the crash-safe OS lock across preflight and all work.
uv run --reinstall-package lokay --reinstall-package fala lokay-daemon --config "${CFG}" --max-passes "${LOKAY_MAX_PASSES:-8}" --outbox "${OUTBOX}" 2>&1 | tee "${LOG}" | tee "${LATEST}"
