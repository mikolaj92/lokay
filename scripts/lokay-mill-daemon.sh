#!/usr/bin/env bash
# Continuous Lokay mill — one pass, invoked by launchd.
# Scope: repos.mikolaj92.yaml (all managed source repos).
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

bootstrap_incident() {
  # Bound bootstrap evidence even when Python/package/config cannot start.
  if [[ -f "${OUTBOX}" ]] && [[ "$(wc -c < "${OUTBOX}")" -ge 65536 ]]; then
    : > "${OUTBOX}"
  fi
  printf '{"health":"preflight_failed","code":"%s"}\n' "$1" >> "${OUTBOX}"
}

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

# Live factory (override with env in the plist if needed)
export LOKAY_MODE="${LOKAY_MODE:-live}"
export LOKAY_EXECUTOR_ENABLED="${LOKAY_EXECUTOR_ENABLED:-1}"
export LOKAY_MERGE_ENABLED="${LOKAY_MERGE_ENABLED:-1}"
export LOKAY_REQUIRE_CHECKS="${LOKAY_REQUIRE_CHECKS:-1}"

if [[ -d "${HOME}/Developer/OSS/Fala/mojo/fala" ]]; then
  export FALA_HOME="${FALA_HOME:-${HOME}/Developer/OSS/Fala}"
fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="${LOG_DIR}/mill-${STAMP}.log"
LATEST="${LOG_DIR}/mill-latest.log"

# Refresh the preflight carrier before starting: uv otherwise preserves stale
# editable installs of Lokay or Fala after either checkout was repaired.
# One Python process owns the crash-safe OS lock across preflight and all work.
uv run --reinstall-package lokay --reinstall-package fala lokay-daemon --config "${CFG}" --max-passes "${LOKAY_MAX_PASSES:-8}" --outbox "${OUTBOX}" 2>&1 | tee "${LOG}" | tee "${LATEST}"
