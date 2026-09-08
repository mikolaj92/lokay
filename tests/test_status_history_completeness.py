"""Dashboard speed must not change the durable history projection (#1097)."""

import json
from datetime import datetime, timezone

from lokay.proc.yield_report import build_report
from lokay.work_units import project_work_units


def test_delivery_before_large_unrelated_event_survives_stale_stop(tmp_path):
    path = tmp_path / "state.jsonl"
    delivery = {"kind": "issue_to_pr", "repo": "a/b", "issue": 7,
                "delivered": True, "pr": 8}
    filler = {"kind": "diagnostic", "detail": "x" * (5 * 1024 * 1024)}
    stale = {"kind": "issue_to_pr", "repo": "a/b", "issue": 7,
             "delivered": False, "stopped": True}
    path.write_text("".join(json.dumps(row) + "\n" for row in [delivery, filler, stale]))

    units = project_work_units(path)

    assert len(units) == 1
    assert units[0]["delivered"] is True
    assert units[0]["pr"] == 8


def test_yield_counts_first_record(tmp_path):
    path = tmp_path / "state.jsonl"
    path.write_text(json.dumps({"kind": "pr_triage", "repo": "a/b",
                               "ts": "2026-09-01T12:00:00Z",
                               "ok": True, "merged": True}) + "\n")

    report = build_report(path, since=datetime(2026, 9, 1, tzinfo=timezone.utc))

    assert report["events"] == 1
    assert report["by_repo"]["a/b"]["merges"] == 1


def test_yield_does_not_assume_timestamp_order(tmp_path):
    path = tmp_path / "state.jsonl"
    rows = [
        {"ts": "2026-09-02T12:00:00Z", "kind": "issue_to_pr", "repo": "a/b"},
        {"ts": "2026-08-01T12:00:00Z", "kind": "diagnostic"},
        {"ts": "2026-09-02T13:00:00Z", "kind": "issue_to_pr", "repo": "a/b"},
    ]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))

    report = build_report(path, since=datetime(2026, 9, 1, tzinfo=timezone.utc))

    assert report["events"] == 2
    assert report["by_repo"]["a/b"]["starts"] == 2


def test_work_units_stream_complete_history_without_read_text(tmp_path, monkeypatch):
    from pathlib import Path

    path = tmp_path / "state.jsonl"
    rows = [
        {"kind": "issue_to_pr", "repo": "a/b", "issue": 1,
         "delivered": True, "pr": 11},
        {"kind": "issue_to_pr", "repo": "a/b", "issue": 2,
         "delivered": False, "work_state": "coding"},
        {"kind": "issue_to_pr", "repo": "a/b", "issue": 1,
         "delivered": False, "stopped": True},
    ]
    # Also cover malformed records and an unterminated final JSONL record.
    path.write_text("broken\n[]\n" + "\n".join(json.dumps(row) for row in rows))
    original_open = Path.open
    opened = []

    def counted_open(self, *args, **kwargs):
        opened.append(self)
        return original_open(self, *args, **kwargs)

    def forbidden_read_text(*args, **kwargs):
        raise AssertionError("work-unit history must be streamed")

    monkeypatch.setattr(Path, "open", counted_open)
    monkeypatch.setattr(Path, "read_text", forbidden_read_text)

    assert project_work_units(path) == [
        {"work_id": "a/b#1", "repo": "a/b", "issue": 1,
         "state": "delivered", "delivered": True, "pr": 11},
        {"work_id": "a/b#2", "repo": "a/b", "issue": 2,
         "state": "coding", "delivered": False},
    ]
    assert opened == [path]
