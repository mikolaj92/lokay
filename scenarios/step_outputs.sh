#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$root"
uv run python - <<'PY'
import json
import sys

def accept(payload):
    if set(payload) != {"result", "artifact"}:
        return False
    if payload["result"] not in ("done", "failed"):
        return False
    if not isinstance(payload["artifact"], str):
        return False
    sys.stdout.write(json.dumps(payload, separators=(",", ":")) + "\n")
    return True

good = {"result": "done", "artifact": "runs/1/plan.md"}
bad = {"result": "maybe", "artifact": "runs/1/plan.md"}
if not accept(good):
    sys.exit("good payload rejected")
sys.stdout = open("/dev/null", "w")
if accept(bad):
    sys.stderr.write("bad payload accepted\n")
    raise SystemExit(1)
sys.stderr.write("step outputs ok\n")
PY
uv run --offline python - <<'PY'
import io
import json
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
from lokay import observe, start, state
from lokay.lock import acquire, release

with tempfile.TemporaryDirectory() as tmp, patch.object(state, 'RUNS', Path(tmp) / 'runs'):
    repo = 'example/retry'
    picked = {'repo': repo, 'issue': 1, 'node': 'check', 'result': 'picked'}
    def action():
        assert acquire('example', repo)['result'] == 'busy'
        raise RuntimeError('network connection failed')
    @start.guarded_step
    def step(picked):
        start._retry(picked, 'check', action)
    with patch('lokay.start.time.sleep', side_effect=AssertionError('sleep under lock')):
        for attempt in (1, 2):
            held = acquire('example', repo)
            assert held['result'] == 'held', held
            with patch('lokay.start.pick', return_value={**picked, 'held': held}), \
                 patch('lokay.start.resume', step), redirect_stdout(io.StringIO()) as out:
                start.main([])
            result = json.loads(out.getvalue().splitlines()[-1])
            assert result == {'result': 'failed', 'reason': 'RuntimeError: network connection failed'}, result
            saved = state.state_read(repo, 1)
            assert saved['failures'] == attempt, saved
            assert saved['retry_at'] > start.time.time() + 60 * 2 ** (attempt - 1) - 2
            assert observe.CURRENT['result'] == 'failed'
            assert observe.CURRENT['last_error'] == saved['reason']
            free = acquire('example', repo)
            assert free['result'] == 'held', free
            release(free)
        rounds = (state.run_dir(repo, 1) / 'rounds.md').read_text()
        assert rounds.count('→ retry later') == 2, rounds
    # Successful intermediate operations must not erase repeated deterministic failures.
    for attempt in (1, 2):
        start.needs_help(picked, 'dirty worktree', 'abc')
        saved = state.state_read(repo, 1)
        assert saved['retry_at'] == 0
        if attempt == 1:
            assert saved['node'] == 'check'
            start._retry(picked, 'merge', lambda: {'result': 'done'})
        else:
            assert saved['node'] == 'plan' and saved['plan_phase'] == 'write'
            assert 'dirty worktree' in saved['plan_prompt']
            assert 'Last state:' in saved['plan_prompt'] and 'Rounds:' in saved['plan_prompt']
    assert '→ Plan: dirty worktree' in (state.run_dir(repo, 1) / 'rounds.md').read_text()
    start._retry(picked, 'check', lambda: {'result': 'done'}, 'done')
    assert state.state_read(repo, 1)['failures'] == 0
    assert observe.CURRENT['last_error'] is None
print('retry: one attempt per tick, persisted backoff, lock release and cleared heartbeat OK')
PY
