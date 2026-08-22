from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from lokay.github_yield import github_delivery


class Run:
    def __init__(self):
        self.calls = 0

    def run_checked(self, spec, *, live):
        self.calls += 1
        if self.calls == 1:
            rows = [{"created_at": "2026-08-19T10:00:00Z", "merged_at": "2026-08-19T10:06:00Z"}]
        else:
            rows = [
                {"created_at": "2026-08-19T10:00:00Z", "closed_at": "2026-08-19T10:05:00Z"},
                {"pull_request": {}, "created_at": "2026-08-19T10:00:00Z", "closed_at": "2026-08-19T10:05:00Z"},
            ]
        return SimpleNamespace(stdout=json.dumps(rows))


def test_github_delivery_counts_dod_and_excludes_pr_shaped_issues():
    out = github_delivery(
        Run(),
        "mikolaj92/lokay",
        since=datetime(2026, 8, 19, 9, tzinfo=timezone.utc),
        hours=8,
    )
    assert out["merged_prs"]["count"] == 1
    assert out["merged_prs"]["per_hour"] == 0.12
    assert out["closed_issues"]["count"] == 1
    assert out["closed_issues"]["median_minutes"] == 5.0


def test_github_delivery_flattens_paginated_json_streams():
    class PaginatedRun:
        def __init__(self):
            self.calls = 0

        def run_checked(self, spec, *, live):
            self.calls += 1
            key = "merged_at" if self.calls == 1 else "closed_at"
            return SimpleNamespace(
                stdout=(
                    json.dumps([{"created_at": "2026-08-19T10:00:00Z", key: "2026-08-19T10:01:00Z"}])
                    + "\n"
                    + json.dumps([{"created_at": "2026-08-19T10:00:00Z", key: "2026-08-19T10:02:00Z"}])
                )
            )

    out = github_delivery(
        PaginatedRun(),
        "mikolaj92/lokay",
        since=datetime(2026, 8, 19, 9, tzinfo=timezone.utc),
        hours=1,
    )
    assert out["merged_prs"]["count"] == 2
    assert out["closed_issues"]["count"] == 2
    source = Path(__file__).resolve().parents[1] / "src" / "lokay" / "github_yield.py"
    assert "Yield pagination is flattened before row access." in source.read_text(
        encoding="utf-8"
    )
