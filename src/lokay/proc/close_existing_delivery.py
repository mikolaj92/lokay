"""Close out one issue whose delivery PR already exists (open or merged)."""

from __future__ import annotations

import argparse
from typing import Any

from lokay.envelope import ok
from lokay.gh_prs import find_pr_fixing_issue
from lokay.proc._common import load_cfg, mutations_allowed, runner
from lokay.proc.closeout import _park_ready


def close(
    *,
    repo: str,
    issue: int,
    config_path: str | None,
    live: bool,
    pr: Any = None,
) -> dict:
    """Existing ai/fix (or merged) delivery is a successful closeout, not no_effect."""
    cfg = load_cfg(argparse.Namespace(config=config_path))
    allowed = mutations_allowed(live_flag=live, cfg=cfg)
    pull = None
    number = None
    if isinstance(pr, dict) and pr.get("number") not in (None, "", 0):
        pull = pr
        try:
            number = int(pr["number"])
        except (TypeError, ValueError):
            number = None
    else:
        try:
            number = int(pr) if pr not in (None, "", 0) else None
        except (TypeError, ValueError):
            number = None
        if number is not None:
            pull = {"number": number}
    if pull is None:
        pull = find_pr_fixing_issue(
            runner(cfg), repo, issue, live=allowed, merged_only=False
        )
    if pull is None:
        return ok(repo=repo, issue=issue, delivered=False, labels_removed=False)
    parked = _park_ready(
        repo=repo, issue=issue, allowed=allowed, config_path=config_path
    )
    return ok(
        repo=repo,
        issue=issue,
        pr=pull.get("number") if isinstance(pull, dict) else number,
        delivered=True,
        labels_removed=bool(parked.get("ok") and parked.get("removed")),
        parked=parked,
        reason="delivery_pr_exists",
    )
