#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .check-local
sandbox=$(mktemp -d "$PWD/.check-local/pending.XXXXXX")
trap 'rm -rf "$sandbox"' EXIT
for phase in seed before before before before before before before before fix after after after after after after after after; do
    env -i HOME="$sandbox" PATH="$PWD/.venv/bin:/usr/bin:/bin" PHASE="$phase" .venv/bin/python - <<'PY'
import os
from lokay import store
from lokay.tick import escalate

repo, issue = 'example/pending', 1
picked = {'repo': repo, 'issue': issue}
phase = os.environ['PHASE']
if phase == 'seed':
    store.state_update(repo, issue, node='check', result='pending', sha='a' * 40,
                       verdict=None, run_rounds=100, no_progress=100, failures=0,
                       progress_diff_fingerprint='broken-diff')
    store.state_update(repo, 2, node='plan', result='queued')
elif phase == 'fix':
    before = store.state_read(repo, issue)
    assert before['sha'] == 'a' * 40
    fields = store.round_fields(before, diff_fingerprint='fixed-diff', completed=False)
    store.state_update(repo, issue, _event={'action': 'fix_complete', 'outcome': {
        'result': 'pushed', 'sha': 'b' * 40, 'previous_sha': before['sha']}},
        sha='b' * 40, **fields)
else:
    before = store.state_read(repo, issue)
    assert escalate(picked) is None
    store.state_update(repo, issue, result='running')
    assert escalate(picked) is None
    store.state_update(repo, issue, result='pending', verdict=None)
    saved = store.state_read(repo, issue)
    assert saved['node'] == 'check' and saved['result'] == 'pending'
    assert saved['verdict'] is None and saved['failures'] == 0
    assert saved['sha'] == ('a' if phase == 'before' else 'b') * 40
    assert saved['run_rounds'] == 100
    assert saved['no_progress'] == (100 if phase == 'before' else 0)
    assert store.state_read(repo, 2)['result'] == 'queued'
PY
done
printf '%s\n' 'pending: 8 persisted waits before and after changed SHA; incomplete Check does not escalate'
