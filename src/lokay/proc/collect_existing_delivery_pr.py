"""Collect an existing open or merged pull request that closes one issue."""

from __future__ import annotations
from lokay.config import Config
from lokay.gh_prs import find_pr_fixing_issue
from lokay.proc.inspect_repo_pr_admission import inspect


def collect(*, runner, repo: str, issue: int, live: bool, config: Config) -> dict:
    admission = inspect(runner=runner, config=config, repo=repo, issue=issue, live=live)
    if not admission["allowed"]:
        return {"ok": True, "existing_delivery": None, "pr_admission": admission}
    try:
        pr = find_pr_fixing_issue(runner, repo, issue, live=live, merged_only=False)
    except Exception:  # noqa: BLE001 - unavailable external evidence denies delivery
        admission = {"allowed": False, "reason": "pr_survey_unavailable"}
        pr = None
    return {"ok": True, "existing_delivery": pr or None, "pr_admission": admission}
