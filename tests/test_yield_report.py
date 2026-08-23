from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from lokay.proc.yield_report import build_report


def test_yield_report_counts_repo_and_semantic_trace(tmp_path: Path):
    state = tmp_path / "state.jsonl"
    rows = [
        {
            "ts": "2026-08-19T10:00:00Z",
            "kind": "issue_to_pr",
            "repo": "a/b",
            "ok": True,
            "pr": 7,
        },
        {
            "ts": "2026-08-19T10:00:30Z",
            "kind": "pr_triage",
            "repo": "a/b",
            "ok": True,
            "pr": 7,
            "merged": True,
        },
        {
            "ts": "2026-08-19T10:01:00Z",
            "kind": "localize",
            "repo": "a/b",
            "result": {
                "semantic": {
                    "kind": "localize",
                    "source": "agent",
                    "status": "completed",
                    "duration_ms": 120,
                }
            },
        },
    ]
    state.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    report = build_report(
        state,
        since=datetime(2026, 8, 19, 9, tzinfo=timezone.utc),
    )
    assert report["by_repo"]["a/b"]["starts"] == 1
    assert report["by_repo"]["a/b"]["prs"] == 1
    assert report["by_repo"]["a/b"]["merges"] == 1
    assert report["semantic"]["localize"]["outcomes"]["agent:completed"] == 1
    assert report["semantic"]["localize"]["average_duration_ms"] == 120
