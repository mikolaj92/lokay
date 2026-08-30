"""Pick one listed issue. Two small functions: leftover walk, then pick."""

import os

from lokay.proc.classify_issue_assignee import mill_of, takeable
from lokay.proc.classify_open_issues import classify
from lokay.proc.walk_issue_leftover import queue


def occupied_repos_of(occupied=None) -> set[str]:
    """Live receipts occupy a repo. Pytest stays empty unless the test passes a set."""
    if occupied is not None:
        return {str(name) for name in occupied if name}
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return set()
    from lokay.proc.issue_delivery_occupancy import live_issue_to_pr_receipts

    return {
        str(row.get("repo") or "")
        for row in live_issue_to_pr_receipts()
        if row.get("repo")
    }


def pick(classified: dict) -> dict:
    if classified.get("route") != "listed":
        return {
            "ok": True,
            "route": "none",
            "reason": classified.get("reason") or "skip",
        }
    rows = list(classified.get("issues") or [])
    if not rows:
        return {"ok": True, "route": "none", "reason": "no_open_issue"}
    leftover = max(0, len(rows) - 1)
    return {
        **dict(rows[0]),
        "ok": True,
        "route": "issue",
        "leftover": leftover,
        "leftover_issues": [dict(row) for row in rows[1:]],
    }


def select(listed: dict, last: dict | None = None, occupied=None) -> dict:
    classified = classify(listed)
    if classified.get("route") != "listed":
        return pick(classified)
    mill = mill_of(listed, last)
    occupied_repos = occupied_repos_of(occupied)
    rows = queue(classified.get("issues"), last, mill=mill, occupied=occupied_repos)
    if not rows:
        listed_rows = list(classified.get("issues") or [])
        takeable_rows = [row for row in listed_rows if takeable(row, mill)]
        if listed_rows and not takeable_rows:
            reason = "foreign_assignee"
        elif takeable_rows and occupied_repos and all(
            str(row.get("repo") or "") in occupied_repos for row in takeable_rows
        ):
            reason = "occupied"
        else:
            reason = "exhausted"
        return {"ok": True, "route": "none", "reason": reason, "leftover": 0}
    return pick({**classified, "issues": rows, "route": "listed"})
