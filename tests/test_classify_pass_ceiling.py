"""Pass ceiling progress is this tick, not historical delivery."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from lokay.proc.classify_pass_ceiling import classify
from lokay.proc.record_inflight_remaining import remaining_from_inflight_working


def _posejdon_event() -> dict:
    return {
        "kind": "issue_to_pr",
        "repo": "mikolaj92/Posejdon",
        "issue": 74,
        "pr": 75,
        "delivered": True,
        "run_id": "lokay-37a8833ab9bc",
        "ts": "2026-09-02T17:10:58.968723+00:00",
        "branch": "ai/fix/74-bug-replacement-planner-leaves-low-conf-a2c2c646",
    }


def _stale_empty_working() -> dict:
    return {
        "remaining_inbox": 0,
        "remaining_ready": 0,
        "remaining_prs": 0,
        "survey_errors": 0,
        "inbox_issues_by_repo": {},
        "ready_by_repo": {},
        "inbox_by_repo": {},
    }


def test_historical_delivery_alone_is_not_this_tick_progress(tmp_path: Path):
    """Live 2026-09-03 restart: Posejdon#74 from yesterday is resume, not progress."""
    (tmp_path / "state.jsonl").write_text(
        json.dumps(_posejdon_event()) + "\n", encoding="utf-8"
    )
    out = classify(state_dir=tmp_path, elapsed_seconds=180.0)
    assert out["health"] == "pass_ceiling"
    assert out["reason"] != "ceiling_with_progress"
    assert out["reason"] == "ceiling_stalled"
    assert out["transitions"] == 0
    assert out["latest_delivery"]["work_id"] == "mikolaj92/Posejdon#74"
    assert out["latest_delivery"]["pr"] == 75
    assert "last_path" not in out
    assert "resume_from" not in out


def test_stale_empty_pass_dir_is_not_inflight_working(tmp_path: Path):
    """Newest factory-pass-* from before this tick is not inflight remaining."""
    stale = tmp_path / "factory-pass-22062-bdb0d8423cf9"
    stale.mkdir()
    (stale / "working.json").write_text(
        json.dumps(_stale_empty_working()), encoding="utf-8"
    )
    stale_mtime = time.time() - 1400
    os.utime(stale, (stale_mtime, stale_mtime))
    os.utime(stale / "working.json", (stale_mtime, stale_mtime))

    since = time.time() - 180.0
    remaining = remaining_from_inflight_working(tmp_path, since=since)
    assert remaining is None


def test_live_restart_ceiling_is_stalled_not_progress(tmp_path: Path):
    """Three live receipts: empty remaining, stale pass dir, old Posejdon delivery."""
    (tmp_path / "state.jsonl").write_text(
        json.dumps(_posejdon_event()) + "\n", encoding="utf-8"
    )
    stale = tmp_path / "factory-pass-22062-bdb0d8423cf9"
    stale.mkdir()
    (stale / "working.json").write_text(
        json.dumps(_stale_empty_working()), encoding="utf-8"
    )
    stale_mtime = time.time() - 1400
    os.utime(stale, (stale_mtime, stale_mtime))
    os.utime(stale / "working.json", (stale_mtime, stale_mtime))
    (tmp_path / "last-pass.json").write_text(
        json.dumps(
            {
                "kind": "pass_receipt",
                "health": "pass_ceiling",
                "remaining": {
                    "inbox": 0,
                    "ready": 0,
                    "ready_with_open_pr": 0,
                    "open_ai_prs": 0,
                    "survey_errors": 0,
                    "by_repo": [],
                },
            }
        ),
        encoding="utf-8",
    )

    from lokay.compose.daemon_cycle import ceiling_remaining

    remaining, source = ceiling_remaining(tmp_path, since=time.time() - 180.0)
    out = classify(
        state_dir=tmp_path,
        elapsed_seconds=180.0,
        remaining=remaining,
        remaining_source=source,
    )
    assert source is None
    assert out["reason"] == "ceiling_stalled"
    assert out["transitions"] == 0
    assert out["latest_delivery"]["work_id"] == "mikolaj92/Posejdon#74"
    assert "remaining_source" not in out or out.get("remaining_source") != "inflight_working"


def test_this_tick_pass_dir_still_counts_as_inflight(tmp_path: Path):
    live = tmp_path / "factory-pass-1-deadbeef"
    live.mkdir()
    (live / "working.json").write_text(
        json.dumps(
            {
                "remaining_inbox": 4,
                "remaining_ready": 1,
                "inbox_issues_by_repo": {
                    "mikolaj92/Temida": [{"number": 4972}, {"number": 4973}]
                },
                "ready_by_repo": {"mikolaj92/Temida": [{"number": 4968}]},
            }
        ),
        encoding="utf-8",
    )
    remaining = remaining_from_inflight_working(tmp_path, since=time.time() - 180.0)
    assert remaining is not None
    assert remaining["inbox"] == 2
    out = classify(
        state_dir=tmp_path,
        elapsed_seconds=180.0,
        remaining=remaining,
        remaining_source="inflight_working",
    )
    assert out["reason"] == "ceiling_with_progress"
    assert out["remaining_source"] == "inflight_working"


def test_activity_transitions_still_mean_progress(tmp_path: Path):
    (tmp_path / "activity.json").write_text(
        json.dumps(
            {
                "path": "executor_department",
                "atom": "list_open_issues",
                "work_id": "mikolaj92/reviewkit#308",
                "repo": "mikolaj92/reviewkit",
                "transitions": 1,
            }
        ),
        encoding="utf-8",
    )
    out = classify(state_dir=tmp_path, elapsed_seconds=180.0)
    assert out["reason"] == "ceiling_with_progress"
    assert out["resume_from"] == "executor_department"
    assert out["work_id"] == "mikolaj92/reviewkit#308"
