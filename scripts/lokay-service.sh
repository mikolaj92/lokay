#!/usr/bin/env bash
# OS caretaker for LaunchAgent ai.mikolaj.lokay.
# Product idle / host-ff / survey live in Fala. This script only leases the
# lokay lock, execs one resident lokay-daemon that schedules repeated bounded
# graphs, logs, and records a bootstrap incident if the process cannot start.
# Plist RunAtLoad + crash KeepAlive is host setup (`--install`), not a
# per-tick rewrite.
set -euo pipefail

HOME="${HOME:-${TMPDIR:-/tmp}/lokay-${UID:-unknown}}"
export HOME
export PATH="${HOME}/.local/bin:${HOME}/.local/share/mise/shims:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"
export LANG="${LANG:-C.UTF-8}"
export TMPDIR="${TMPDIR:-/tmp}"
# The review reads OCR_LLM_API_KEY. launchd starts this script with a clean
# environment, so load the key file the session uses and map the name across.
CLIENT_ENV="${HOME}/.config/agent-memory/client.env"
if [[ -f "${CLIENT_ENV}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${CLIENT_ENV}"
  set +a
fi
if [[ -z "${OCR_LLM_API_KEY:-}" && -n "${TDAI_MEMORY_API_KEY:-}" ]]; then
  export OCR_LLM_API_KEY="${TDAI_MEMORY_API_KEY}"
fi
# pi hangs instead of picking a model unless the provider is named.
export PI_PROVIDER="${PI_PROVIDER:-omniroute}"
export PI_MODEL="${PI_MODEL:-pi}"

export LOKAY_ROOT="${LOKAY_ROOT:-${HOME}/Developer/lokay/main}"
ROOT="${LOKAY_ROOT}"
export PATH="${ROOT}/.venv/bin:${PATH}"
UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-${ROOT}/.venv}"
export UV_PROJECT_ENVIRONMENT
export LOKAY_CONFIG="${LOKAY_CONFIG:-${ROOT}/config.yaml}"
CFG="${LOKAY_CONFIG}"
# Do not default LOKAY_REPO_SCOPE. Empty = full catalog (~30). Oil-only
# mikolaj92/lokay is an explicit clamp, not the LaunchAgent default.
LOKAY_HOME="${HOME}/.lokay"
LOG_DIR="${LOKAY_LOG_DIR:-${LOKAY_HOME}/logs}"
OUTBOX="${LOKAY_HOME}/preflight-bootstrap-incidents.log"
LOKAY_LAUNCHD_LABEL="${LOKAY_LAUNCHD_LABEL:-ai.mikolaj.lokay}"
LOKAY_LAUNCHD_PLIST="${LOKAY_LAUNCHD_PLIST:-${HOME}/Library/LaunchAgents/${LOKAY_LAUNCHD_LABEL}.plist}"
# Seconds between successive graphs inside the resident daemon.
LOKAY_DAEMON_INTERVAL="${LOKAY_DAEMON_INTERVAL:-15}"

bootstrap_incident() {
  if [[ -f "${OUTBOX}" ]] && [[ "$(wc -c < "${OUTBOX}")" -ge 65536 ]]; then
    : > "${OUTBOX}"
  fi
  printf '{"health":"preflight_failed","code":"%s"}\n' "$1" >> "${OUTBOX}"
}

write_host_plist() {
  # Host setup only. Missing plist stays missing. Do not invent a job.
  # plutil only — the tick path never rewrites the plist. One lifecycle
  # policy: start at load, restart on crash. No StartInterval: the daemon is
  # resident and schedules its own repeated graphs.
  local plist="${LOKAY_LAUNCHD_PLIST}"
  [[ -f "${plist}" ]] || return 0
  command -v plutil >/dev/null 2>&1 || return 0
  plutil -remove StartInterval "${plist}" >/dev/null 2>&1 || true
  plutil -replace RunAtLoad -bool true "${plist}" >/dev/null 2>&1 || true
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
# Retain logs: age alone does not prove delivery or release recovery evidence.
if [[ ! -x "${ROOT}/.venv/bin/python" ]]; then
  bootstrap_incident "python_environment_unavailable"
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

# Host/daemon ambient for effect atoms that call real `gh` (push/merge/close/PR).
# The harness inherits this host environment and runs with the user's permissions.
# LaunchAgent plist must not embed tokens; mint GH_TOKEN from gh keyring when missing.
if [[ -z "${GH_TOKEN:-}" ]] && command -v gh >/dev/null 2>&1; then
  _tok="$(gh auth token 2>/dev/null || true)"
  if [[ -n "${_tok}" ]]; then
    export GH_TOKEN="${_tok}"
  fi
  unset _tok
fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="${LOG_DIR}/lokay-${STAMP}.log"
LATEST="${LOG_DIR}/lokay-latest.log"
printf '%s\n' '{"ok":true,"health":"current","reason":"starting"}' | tee "${LOG}" >"${LATEST}"

# Each graph stays bounded inside the daemon: the Fala daemon_entry graph
# enforces the pass ceiling (LOKAY_PASS_CEILING_SECONDS, default 7200) via
# SIGALRM and writes the classified receipt itself. No caretaker watchdog is
# needed and none would see graph boundaries.

stop_cycle_tree() {
  # Stop every descendant of this daemon except a registered detached
  # issue_to_pr process group created with start_new_session. Fala effectors also use new sessions, so session
  # identity alone cannot prove that a process owns durable work.
  "${ROOT}/.venv/bin/python" -m lokay.proc.stop_cycle_tree "$1" "${LOKAY_HOME}/cycle" >/dev/null 2>&1 || true
}

DAEMON_PID=""
shutdown_service() {
  trap - TERM INT
  if [[ -n "${DAEMON_PID:-}" ]]; then
    # Forward the signal first so the resident daemon drains: it finishes the
    # current bounded graph, releases lokay.lock, and exits 0 (crash-only
    # KeepAlive stays quiet). Stopping the cycle tree concludes that graph
    # promptly; registered detached workers keep their receipts.
    kill -TERM "${DAEMON_PID}" 2>/dev/null || true
    stop_cycle_tree "${DAEMON_PID}"
    wait "${DAEMON_PID}" 2>/dev/null || true
  fi
  cp "${LOG}" "${LATEST}" 2>/dev/null || true
  exit 0
}
trap shutdown_service TERM INT

set +e
# Job control gives the daemon its own process group (nested effectors and
# detached workers group separately; see stop_cycle_tree).
set -m
"${ROOT}/.venv/bin/lokay-daemon" --config "${CFG}" --max-passes "${LOKAY_MAX_PASSES:-8}" --interval "${LOKAY_DAEMON_INTERVAL}" --outbox "${OUTBOX}" >>"${LOG}" 2>&1 &
DAEMON_PID=$!
wait "${DAEMON_PID}"
LOKAY_RC=$?
cp "${LOG}" "${LATEST}" 2>/dev/null || true
if [[ "${LOKAY_RC}" -ne 0 ]]; then
  bootstrap_incident "daemon_exec"
fi
exit "${LOKAY_RC}"
