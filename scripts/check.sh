#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
# Explicit inventory: a missing scenario is a failure, not a shorter green suite.
scenarios='
build check ci ci_not_run docs_only_fix no_new_tests setup_deps darkfactory darkfactory_canary decision_contract fix host_down host_guard
issue_flow lock merge merge_sha no_legacy_imports observability outside_worktree plan
push_guard safety start_pick start_plan start_resume step_outputs suite worktree
'
required=0
for name in $scenarios; do
    test -f "scenarios/$name.sh" || { echo "missing scenario: $name" >&2; exit 1; }
    bash -n "scenarios/$name.sh"
    required=$((required + 1))
done
executed=0
for name in $scenarios; do
    echo "=== scenarios/$name.sh ==="
    bash "scenarios/$name.sh"
    executed=$((executed + 1))
done
printf 'scenarios: %s/%s; errors=0\n' "$executed" "$required"
