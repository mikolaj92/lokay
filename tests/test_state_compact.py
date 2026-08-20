from __future__ import annotations

import json
from pathlib import Path

from lokay.child_harvest import _index_issue_to_pr_log
from lokay.proc.yield_report import build_report
from lokay.state_compact import compact_state


def test_compaction_keeps_recovery_and_semantic_facts(tmp_path: Path):
    state = tmp_path / "state.jsonl"
    event = {
        "ts": "2026-08-19T10:00:00Z",
        "kind": "issue_to_pr",
        "repo": "mikolaj92/lokay",
        "issue": 7,
        "ok": False,
        "reason": "zero_diff",
        "run_id": "run-7",
        "terminal": {"huge": "x" * 10000},
        "result": {"semantic": {"kind": "localize", "source": "agent", "status": "completed", "duration_ms": 12}},
    }
    state.write_text(json.dumps(event) + "\n", encoding="utf-8")

    result = compact_state(state, min_bytes=0)

    assert result["compacted"] is True
    assert state.stat().st_size < 1000
    _last, history = _index_issue_to_pr_log(state)
    assert history[("mikolaj92/lokay", 7)] == [("run-7", "zero_diff")]
    report = build_report(state, since=__import__("datetime").datetime(2026, 8, 19, 9, tzinfo=__import__("datetime").timezone.utc))
    assert report["semantic"]["localize"]["average_duration_ms"] == 12
