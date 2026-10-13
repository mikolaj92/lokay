#!/bin/bash
set -eu
cd "$(dirname "$0")/.."
if [ -x .venv/bin/python ]; then
    exec .venv/bin/python -m lokay.dashboard --host 0.0.0.0 --port "${LOKAY_DASHBOARD_PORT:-8010}"
fi
exec uv run --frozen python -m lokay.dashboard --host 0.0.0.0 --port "${LOKAY_DASHBOARD_PORT:-8010}"
