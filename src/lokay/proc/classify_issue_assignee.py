"""Whether a listed task is lokay-owned. Foreign assignees are not takeable.

Today the list carries Issue.assignees. Empty or only the configured lokay
(default mikolaj92) may be taken. Anyone else — alone or beside the lokay —
is foreign. Selection skips; assign must not add the lokay beside them.
"""

from __future__ import annotations

DEFAULT_LOKAY = "mikolaj92"


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


def lokay_of(*sources: dict | None, default: str = DEFAULT_LOKAY) -> str:
    for src in sources:
        if not isinstance(src, dict):
            continue
        name = str(src.get("assignee") or "").strip()
        if name:
            return name
    return default


def foreign(row: dict | None, lokay: str) -> list[str]:
    needle = (lokay or DEFAULT_LOKAY).strip().lower()
    return [name for name in identities(row) if name.lower() != needle]


def takeable(row: dict | None, lokay: str) -> bool:
    return not foreign(row, lokay)


def classify(row: dict | None, lokay: str) -> dict:
    others = foreign(row, lokay)
    if others:
        return {
            "ok": True,
            "route": "skip",
            "reason": "foreign_assignee",
            "foreign": others,
        }
    return {"ok": True, "route": "take", "reason": None}
