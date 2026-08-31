"""Decide whether another issue_row child should run. Two small functions."""

from __future__ import annotations

CONTINUE = "continue"
IDLE = "idle"
CAP = "cap"
_LAUNCHED = frozenset({"started", "pr", "new_pr"})


def leftover_of(row: dict) -> tuple[int, list[dict]]:
    """Leftover listed issues after one issue_row. Empty means the inbox is done."""
    result = row.get("result") if isinstance(row.get("result"), dict) else row
    leftover_issues = [
        item for item in list((result or {}).get("leftover_issues") or []) if isinstance(item, dict)
    ]
    leftover = int((result or {}).get("leftover") or 0)
    if leftover_issues:
        leftover = max(leftover, len(leftover_issues))
    return leftover, leftover_issues


def launched_of(row: dict) -> bool:
    result = row.get("result") if isinstance(row.get("result"), dict) else row
    return str((result or {}).get("launched") or "") in _LAUNCHED


def classify(
    row: dict, *, spent: int, budget: int, bound_any: bool = False
) -> dict:
    leftover, leftover_issues = leftover_of(row)
    if leftover <= 0:
        return {"ok": True, "route": IDLE, "leftover": 0, "leftover_issues": []}
    cap = max(0, int(budget))
    if (launched_of(row) or bound_any) and (cap == 0 or int(spent) >= cap):
        return {
            "ok": True,
            "route": CAP,
            "leftover": leftover,
            "leftover_issues": leftover_issues,
        }
    return {
        "ok": True,
        "route": CONTINUE,
        "leftover": leftover,
        "leftover_issues": leftover_issues,
    }
