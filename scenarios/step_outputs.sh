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
uv run --offline python - <<'PY'
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, call, patch
from lokay import run

clock = MagicMock(return_value=9.0)
token = run.tick_deadline.set(10.0)
try:
    with patch.object(run.time, 'monotonic', clock):
        run.check_deadline()
        clock.return_value = 10.0
        try:
            run.check_deadline()
        except run.TickExpired:
            pass
        else:
            raise AssertionError('deadline boundary accepted')
        with patch.object(run.subprocess, 'Popen') as popen:
            try:
                run.run_process(['fixture'])
            except run.TickExpired:
                pass
            else:
                raise AssertionError('process started at deadline')
            popen.assert_not_called()

        clock.return_value = 9.0
        for operation, effective in ((30, 1), (0.25, 0.25), (1, 1)):
            process = MagicMock(pid=123, returncode=0)
            process.__enter__.return_value = process
            process.communicate.return_value = ('stdout', 'stderr')
            with patch.object(run.subprocess, 'Popen', return_value=process):
                run.run_process(['fixture'], timeout=operation)
            process.communicate.assert_called_once_with(timeout=effective)
            process.reset_mock()
            # Starting the process also consumes the tick budget.
            with patch.object(run.subprocess, 'Popen', return_value=process), \
                 patch.object(run.time, 'monotonic', side_effect=[9.0, 9.5]):
                run.run_process(['fixture'], timeout=operation)
            process.communicate.assert_called_once_with(timeout=min(effective, 0.5))
            for drain_timeout in (False, True):
                for vanished in (False, True):
                    process.reset_mock()
                    process.returncode = None if drain_timeout else -signal.SIGKILL
                    process.communicate.side_effect = [
                        subprocess.TimeoutExpired(['fixture'], effective, output='early'),
                        subprocess.TimeoutExpired(['fixture'], 5, output='partial stdout', stderr='partial stderr')
                        if drain_timeout else ('partial stdout', 'partial stderr')]
                    with patch.object(run.subprocess, 'Popen', return_value=process), \
                         patch.object(run.os, 'killpg', side_effect=ProcessLookupError if vanished else None) as killpg, \
                         patch.object(run.time, 'monotonic', side_effect=[9.0, 9.0, 9.0, 9.0, 14.0]):
                        try:
                            run.run_process(['fixture'], timeout=operation)
                        except run.TickExpired:
                            assert effective == 1, 'operation timeout became tick expiry'
                        except subprocess.TimeoutExpired as error:
                            assert effective == 0.25, 'tick expiry became operation timeout'
                            assert error.timeout == operation
                            assert error.output == 'partial stdout' and error.stderr == 'partial stderr'
                        else:
                            raise AssertionError('timeout swallowed')
                        killpg.assert_called_once_with(123, signal.SIGKILL)
                    assert process.communicate.call_args_list == [call(timeout=effective), call(timeout=5)]
                    if drain_timeout:
                        process.wait.assert_called_once_with(timeout=0)
                    else:
                        process.wait.assert_not_called()
            process.communicate.side_effect = None
        with patch.object(run.time, 'sleep', side_effect=lambda seconds: setattr(clock, 'return_value', 10.0)) as sleep:
            try:
                run.retry_sleep(60)
            except run.TickExpired:
                pass
            else:
                raise AssertionError('wait did not expire')
            sleep.assert_called_once_with(1.0)
            sleep.reset_mock()
            try:
                run.retry_sleep(60)
            except run.TickExpired:
                pass
            else:
                raise AssertionError('wait accepted at deadline')
            sleep.assert_not_called()
finally:
    run.tick_deadline.reset(token)

assert run.tick_deadline.get() is None
with tempfile.TemporaryDirectory() as tmp:
    for limit, expected in ((None, 3600), (7200, 3600), (0.25, 0.25)):
        process = MagicMock(pid=123, returncode=0)
        process.__enter__.return_value = process
        process.communicate.return_value = ('stdout', 'stderr')
        with patch.object(run.subprocess, 'Popen', return_value=process) as popen:
            result = run.run_process(['fixture'], cwd=tmp, timeout=limit)
        process.communicate.assert_called_once_with(timeout=expected)
        assert result.stdout == 'stdout' and result.stderr == 'stderr'
        assert popen.call_args.kwargs['start_new_session'] is True
        process.wait.assert_not_called()

    for limit in (0, -1, float('nan'), float('inf')):
        with patch.object(run.subprocess, 'Popen') as popen:
            try:
                run.run_process(['fixture'], timeout=limit)
            except ValueError:
                pass
            else:
                raise AssertionError(f'invalid timeout accepted: {limit}')
            popen.assert_not_called()

    process = MagicMock(pid=123, returncode=-signal.SIGKILL)
    process.__enter__.return_value = process
    process.communicate.side_effect = [subprocess.TimeoutExpired(['fixture'], 0.25), ('partial stdout', 'partial stderr')]
    with patch.object(run.subprocess, 'Popen', return_value=process), patch.object(run.os, 'killpg') as killpg:
        try:
            run.run_process(['fixture'], timeout=0.25)
        except subprocess.TimeoutExpired as error:
            assert error.cmd == ['fixture'] and error.timeout == 0.25
            assert error.output == 'partial stdout' and error.stderr == 'partial stderr'
        else:
            raise AssertionError('process timeout swallowed')
        killpg.assert_called_once_with(123, signal.SIGKILL)
    assert process.communicate.call_args_list[0] == call(timeout=0.25)
    assert len(process.communicate.call_args_list) == 2
    assert 0 < process.communicate.call_args_list[1].kwargs['timeout'] <= 5
    process.wait.assert_not_called()

    argv = [sys.executable, '-c',
            'import sys, time; print("ready", flush=True); '
            'print("waiting", file=sys.stderr, flush=True); time.sleep(30)']
    try:
        run.run_process(argv, cwd=tmp, timeout=0.05)
    except subprocess.TimeoutExpired as error:
        assert error.cmd == argv and error.timeout == 0.05
        assert error.output == 'ready\n' and error.stderr == 'waiting\n'
    else:
        raise AssertionError('real process timeout swallowed')

# A real child inherits the process group and must not write after expiry.
with tempfile.TemporaryDirectory() as tmp:
    marker = Path(tmp) / 'late'
    pids = Path(tmp) / 'pids'
    child = 'import time; from pathlib import Path; time.sleep(2); Path(' + repr(str(marker)) + ').touch()'
    parent = ('import os, subprocess, sys, time; from pathlib import Path; '
              'p = subprocess.Popen([sys.executable, "-c", ' + repr(child) + ']); '
              'Path(' + repr(str(pids)) + ').write_text(f"{os.getpid()} {p.pid}"); time.sleep(30)')
    started = time.monotonic()
    token = run.tick_deadline.set(started + 0.75)
    try:
        try:
            run.run_process([sys.executable, '-c', parent], timeout=30)
        except run.TickExpired:
            pass
        else:
            raise AssertionError('real tick timeout swallowed')
    finally:
        run.tick_deadline.reset(token)
    assert time.monotonic() - started < 12, 'cleanup exceeded tolerance'
    parent_pid, child_pid = map(int, pids.read_text().split())
    # An orphan may briefly remain a zombie; it cannot run or write the marker.
    for pid in (parent_pid, child_pid):
        status = subprocess.run(['ps', '-o', 'stat=', '-p', str(pid)], capture_output=True, text=True).stdout.strip()
        assert not status or status.startswith('Z'), (pid, status)
    time.sleep(2)
    assert not marker.exists(), 'child survived tick expiry'

print('tick primitives: boundary=2; waits=2; caps=3; invalid=4; cleanup=1; real_timeout=1; real_tick_group=1')
PY
