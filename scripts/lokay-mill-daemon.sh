#!/usr/bin/env bash
# Continuous Lokay mill — one pass, invoked by launchd.
# Scope: repos.mikolaj92.yaml (all managed source repos).
set -euo pipefail

export PATH="${HOME}/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"

ROOT="${LOKAY_ROOT:-${HOME}/Developer/OSS/lokay}"
CFG="${LOKAY_CONFIG:-${ROOT}/config.yaml}"
LOG_DIR="${LOKAY_LOG_DIR:-${HOME}/.lokay/logs}"
mkdir -p "${LOG_DIR}"

cd "${ROOT}"

# Live factory (override with env in the plist if needed)
export LOKAY_MODE="${LOKAY_MODE:-live}"
export LOKAY_EXECUTOR_ENABLED="${LOKAY_EXECUTOR_ENABLED:-1}"
export LOKAY_AGENT="${LOKAY_AGENT:-grok}"
export LOKAY_MERGE_ENABLED="${LOKAY_MERGE_ENABLED:-1}"
# Product repos often have CI; set 0 only if you accept merge without checks.
export LOKAY_REQUIRE_CHECKS="${LOKAY_REQUIRE_CHECKS:-1}"

if [[ -d "${HOME}/Developer/OSS/Fala/mojo/fala" ]]; then
  export FALA_HOME="${FALA_HOME:-${HOME}/Developer/OSS/Fala}"
fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="${LOG_DIR}/mill-${STAMP}.log"
LATEST="${LOG_DIR}/mill-latest.log"

{
  echo "=== lokay-mill-daemon ${STAMP} ==="
  echo "ROOT=${ROOT} CFG=${CFG}"
  echo "MODE=${LOKAY_MODE} AGENT=${LOKAY_AGENT} EXEC=${LOKAY_EXECUTOR_ENABLED} MERGE=${LOKAY_MERGE_ENABLED} CHECKS=${LOKAY_REQUIRE_CHECKS}"
  uv run lokay-repos --config "${CFG}" 2>&1 | head -c 2000 || true
  echo "--- mill ---"
  # Bounded passes so a single fire cannot hang forever
  uv run lokay-mill --config "${CFG}" --live --max-passes "${LOKAY_MAX_PASSES:-8}" 2>&1
  echo "--- status ---"
  uv run lokay status --config "${CFG}" 2>&1 || true
  echo "=== done ${STAMP} ==="
} | tee "${LOG}" | tee "${LATEST}"

exit 0
