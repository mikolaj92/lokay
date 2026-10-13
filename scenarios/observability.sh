#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
PYTHONPATH=src python3 - <<'PY'
import contextlib
import io
import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
from lokay.cli import main
from lokay import observe, state
from lokay.gh import check_comment, comment_upsert, fit_body, pr_create, pr_set_body

with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, HOME=tmp, LOKAY_TICK_SECONDS="0.02"):
    with patch.object(state, "RUNS", Path(tmp) / "runs"), patch.object(observe, "RUNS", Path(tmp) / "runs"):
        with observe.ticking():
            state.state_update("example/repo", 7, node="check", result="running")
            path = Path(tmp) / ".lokay/heartbeat.json"
            def wait_heartbeat(matches):
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    if path.exists():
                        beat = json.loads(path.read_text())
                        if matches(beat):
                            return beat
                    time.sleep(.01)
                raise AssertionError('heartbeat did not publish the expected state')
            first = wait_heartbeat(lambda beat: beat.get('issue') == 7
                                   and beat.get('node') == 'check')
            state.state_update("example/repo", 7, failures=1, reason="retry")
            second = wait_heartbeat(lambda beat: beat.get('failures') == 1
                                    and beat.get('last_error') == 'retry')
            assert second["time"] != first["time"]
            assert second["node_since"] == first["node_since"]
            assert second["issue"] == 7 and second["node"] == "check"
            assert second['result'] == 'failed' and second['failures'] == 1
            assert second['last_error'] == 'retry'
            state.state_update('example/repo', 7, failures=0, reason=None)
            cleared = observe.heartbeat(**observe.CURRENT)
            assert cleared['result'] != 'failed' and cleared['failures'] == 0
            assert cleared['last_error'] is None
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            assert main(["status"]) == 0
        assert "example/repo" in output.getvalue() and "check" in output.getvalue()
        calls = []
        def gh(args):
            calls.append(args)
            return 0, "[]" if args[:2] == ["issue", "list"] else "", ""
        with patch.object(observe, "_gh", gh):
            assert observe.monitor()["result"] == "ok"
            # The issue clock survives Check ↔ Fix and a new tick.
            started = time.time() - 7200
            state.state_update('example/repo', 7, issue_since=started, last_attempt=time.time())
            with observe.ticking():
                for node in ('fix', 'check', 'fix', 'check'):
                    state.state_update('example/repo', 7, node=node)
                    assert state.state_read('example/repo', 7)['issue_since'] == started
            alarm = observe.monitor()
            assert alarm['result'] == 'stalled' and any('Issue 7 age' in r for r in alarm['reasons'])
            assert calls[-1][calls[-1].index('--title') + 1] == 'lokay-stalled'
            state.state_update('example/repo', 7, result='merged', failures=0)
            assert state.state_read('example/repo', 7)['issue_since'] is None
            observe.heartbeat(**observe.CURRENT)
            assert observe.monitor()['result'] == 'ok'
            state.state_update('example/repo', 7, failures=3, reason='same error')
            observe.heartbeat(**observe.CURRENT)
            assert any('Failures: 3; last_error: same error' in r for r in observe.monitor()['reasons'])
            state.state_update('example/repo', 7, failures=0, reason=None)
            for reason in ('idle_backoff', 'host_down'):
                observe.heartbeat(result='idle', idle_reason=reason)
                assert f'Idle: {reason}' in observe.monitor()['reasons']
            observe.heartbeat(result='running', idle_reason=None, queue_since=started)
            assert any('No merge with queued work' in r for r in observe.monitor()['reasons'])
            observe.heartbeat(result='idle', idle_reason='no_work', **{'failures': 0})
            assert observe.monitor()['result'] == 'ok'
            beat = json.loads(path.read_text())
            beat["node_since"] = time.time() - 7200
            path.write_text(json.dumps(beat))
            assert observe.monitor()["result"] == "stalled"
            assert calls[-1][:2] == ["issue", "create"]
            beat["node"] = None
            beat["time"] = "2000-01-01T00:00:00+00:00"
            path.write_text(json.dumps(beat))
            assert "Heartbeat age" in observe.monitor()["reasons"][0]
        with patch.object(observe, "_gh", return_value=(0, '[{"title":"lokay-stalled","number":1}]', "")) as gh:
            observe.monitor()
            assert gh.call_count == 1
        with patch("lokay.gh._gh", lambda args: (calls.append(args) or 0, "url", "")):
            check_comment("example/repo", 1, 2, {"sha":"abc", "result":"fix", "uwagi":[{"plik":"code.py"}]}, {"result":"red"})
            assert "code.py" in calls[-1][-1] and "red" in calls[-1][-1]
            log = "SUMMARY\n" + "ą" * 99984 + "\nFAILURE"
            assert len(log) == 100000
            assert fit_body("short") == "short"
            fitted = fit_body(log)
            assert len(fitted) <= 60000 and fitted == fit_body(log)
            assert fitted.startswith("SUMMARY\n") and fitted.endswith("\nFAILURE")
            omitted = 99984 - fitted.count("ą")
            assert f"[{omitted} znaków logu pominięto; pełny log w ~/.lokay/runs]" in fitted
            for publish in (
                lambda: pr_create("example/repo", "lokay/7", "title", log, 7),
                lambda: pr_set_body("example/repo", 1, log, 7),
            ):
                publish()
                body = calls[-1][-1]
                assert len(body) <= 60000 and body.startswith("SUMMARY\n")
                assert body.endswith("\nFAILURE\n\nCloses #7\n\nOpened by lokay.\n")
            check_comment("example/repo", 1, 2, {"sha": "abc", "result": "fix"},
                          {"result": "red", "failed": [log]})
            assert len(calls[-1][-1]) <= 60000
            assert calls[-1][-1].startswith("### Lokay Check 2\n")
            assert "FAILURE" in calls[-1][-1]
        for comments in ([], [{"id": 7, "body": "<!-- lokay-check -->"}]):
            with patch("lokay.gh._gh", lambda args: (
                calls.append(args) or 0, json.dumps({"comments": comments}), ""
            )):
                comment_upsert("example/repo", 1, "lokay-check", log)
                body = calls[-1][-1].removeprefix("body=")
                assert len(body) <= 60000
                assert body.startswith("<!-- lokay-check -->\nSUMMARY\n")
                assert body.endswith("\nFAILURE")
print("observability: heartbeat during work, stable node age, status, alarms, deduplication, Check comment OK")
PY
