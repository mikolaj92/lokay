"""Collect an existing open or merged pull request that closes one issue."""

from __future__ import annotations
from lokay.gh_prs import find_pr_fixing_issue


def collect(*, runner, repo: str, issue: int, live: bool) -> dict:
    pr = find_pr_fixing_issue(runner, repo, issue, live=live, merged_only=False)
    return {"ok": True, "existing_delivery": pr or None}
