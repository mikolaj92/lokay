"""Purely clear stuck rows proven CLOSED by catalog facts."""

from lokay.child_harvest import _as_int
from lokay.stuck import clear_issue


def clear(facts: dict) -> dict:
    stuck = dict(facts.get("stuck") or {})
    closed = {k: set(v) for k, v in (facts.get("closed_catalog") or {}).items()}
    for key in list(stuck.get("issues") or {}):
        repo, sep, num = key.rpartition("#")
        issue = _as_int(num)
        if sep and issue in closed.get(repo, set()):
            clear_issue(stuck, repo, issue)
    return {**facts, "stuck": stuck}
