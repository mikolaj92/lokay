"""Multiple dashboard windows share a complete streaming read."""

import json
from datetime import datetime, timezone
from pathlib import Path

from lokay.proc import yield_report


def test_windows_read_history_once_without_materializing_whole_file(tmp_path, monkeypatch):
    path = tmp_path / "state.jsonl"
    rows = [
        {"ts": "2026-09-02T10:00:00Z", "kind": "issue_to_pr", "repo": "a/b", "ok": True, "pr": 7},
        {"ts": "2026-09-01T10:00:00Z", "kind": "pr_triage", "repo": "a/b", "ok": True, "merged": True},
        {"ts": "2026-09-02T11:00:00Z", "kind": "localize", "semantic": {
            "kind": "localize", "source": "agent", "status": "completed", "duration_ms": 120}},
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows))
    windows = {
        "1h": datetime(2026, 9, 2, 10, 30, tzinfo=timezone.utc),
        "24h": datetime(2026, 9, 2, tzinfo=timezone.utc),
        "7d": datetime(2026, 8, 26, tzinfo=timezone.utc),
    }
    expected = {label: yield_report.build_report(path, since=since)
                for label, since in windows.items()}
    opened = []
    original_open = Path.open

    def counted_open(self, *args, **kwargs):
        opened.append(self)
        return original_open(self, *args, **kwargs)

    def forbidden_read_text(*args, **kwargs):
        raise AssertionError("history must be streamed, not read_text().splitlines()")

    monkeypatch.setattr(Path, "open", counted_open)
    monkeypatch.setattr(Path, "read_text", forbidden_read_text)

    actual = yield_report.build_reports(path, windows=windows)

    assert actual == expected
    assert opened == [path]
    assert actual["7d"]["events"] == 3
    assert actual["24h"]["events"] == 2
    assert actual["1h"]["events"] == 1


def test_missing_history_has_empty_report_for_each_window(tmp_path):
    since = datetime(2026, 9, 1, tzinfo=timezone.utc)
    path = tmp_path / "missing"
    expected = yield_report.build_report(path, since=since)
    assert yield_report.build_reports(path, windows={"day": since}) == {"day": expected}
