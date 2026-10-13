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
from lokay.gh import check_comment

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
print("observability: heartbeat during work, stable node age, status, alarms, deduplication, Check comment OK")
PY
