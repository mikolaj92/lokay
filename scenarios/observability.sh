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
            time.sleep(.06)
            path = Path(tmp) / ".lokay/heartbeat.json"
            first = json.loads(path.read_text())
            state.state_update("example/repo", 7, reason="retry")
            time.sleep(.06)
            second = json.loads(path.read_text())
            assert second["time"] != first["time"]
            assert second["node_since"] == first["node_since"]
            assert second["issue"] == 7 and second["node"] == "check"
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
