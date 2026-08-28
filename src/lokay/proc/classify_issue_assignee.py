"""Whether a listed task is mill-owned. Foreign assignees are not takeable.

Today the list carries Issue.assignees. Empty or only the configured mill
(default mikolaj92) may be taken. Anyone else — alone or beside the mill —
is foreign. Selection skips; assign must not add the mill beside them.
"""

from __future__ import annotations

DEFAULT_MILL = "mikolaj92"


def identities(row: dict | None) -> list[str]:
    """Assignee identities on one row. Strings or GitHub {login} objects."""
    if not isinstance(row, dict):
        return []
    out: list[str] = []
    for item in list(row.get("assignees") or []):
        if isinstance(item, dict):
            login = str(item.get("login") or "").strip()
        else:
            login = str(item or "").strip()
        if login:
            out.append(login)
    return out


def mill_of(*sources: dict | None, default: str = DEFAULT_MILL) -> str:
    for src in sources:
        if not isinstance(src, dict):
            continue
        name = str(src.get("assignee") or "").strip()
        if name:
            return name
    return default


def foreign(row: dict | None, mill: str) -> list[str]:
    needle = (mill or DEFAULT_MILL).strip().lower()
    return [name for name in identities(row) if name.lower() != needle]


def takeable(row: dict | None, mill: str) -> bool:
    return not foreign(row, mill)


def classify(row: dict | None, mill: str) -> dict:
    others = foreign(row, mill)
    if others:
        return {
            "ok": True,
            "route": "skip",
            "reason": "foreign_assignee",
            "foreign": others,
        }
    return {"ok": True, "route": "take", "reason": None}
