from __future__ import annotations

import json
from datetime import datetime, timezone
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
