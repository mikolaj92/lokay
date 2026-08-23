"""Collect complete merged-state evidence for PRs referenced by one issue."""

from __future__ import annotations
from lokay.intake import referenced_pr_numbers
from lokay.intake_io import merged_prs
from lokay.models import Issue


def collect(*, runner, repo: str, issue_data: dict, live: bool) -> dict:
    issue = Issue.from_dict(issue_data)
    numbers = referenced_pr_numbers(issue)
    try:
        merged = merged_prs(runner, repo, numbers, live=live)
    except Exception as exc:
        return {
            "ok": True,
            "collected": False,
            "reason": str(exc),
            "probe_failed": True,
            "merged_prs": [],
        }
    return {
        "ok": True,
        "collected": True,
        "referenced_prs": numbers,
        "merged_prs": merged,
        "additional_evidence": {"referenced_prs": numbers, "merged_prs": merged},
    }
