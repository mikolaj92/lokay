"""Close one split parent after child and tracker effects succeed."""

from __future__ import annotations
from lokay.gh_issues import close_issue


def apply(*, runner, repo: str, issue: int, live: bool) -> dict:
    if not live:
        return {"ok": True, "planned": True, "verdict": "split"}
    close_issue(runner, repo, issue, live=True)
    return {"ok": True, "applied": True, "verdict": "split"}
