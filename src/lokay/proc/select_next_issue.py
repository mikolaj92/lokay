"""Pick one listed issue. Two small functions: leftover walk, then pick."""

from lokay.proc.classify_issue_assignee import mill_of, takeable
from lokay.proc.classify_open_issues import classify
from lokay.proc.walk_issue_leftover import queue


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


def select(listed: dict, last: dict | None = None) -> dict:
    classified = classify(listed)
    if classified.get("route") != "listed":
        return pick(classified)
    mill = mill_of(listed, last)
    rows = queue(classified.get("issues"), last, mill=mill)
    if not rows:
        listed_rows = list(classified.get("issues") or [])
        reason = (
            "foreign_assignee"
            if listed_rows and all(not takeable(row, mill) for row in listed_rows)
            else "exhausted"
        )
        return {"ok": True, "route": "none", "reason": reason, "leftover": 0}
    return pick({**classified, "issues": rows, "route": "listed"})
