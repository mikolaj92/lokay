"""Pick one operator-labeled issue. Deterministic, no triage, no catalog sieve."""

from __future__ import annotations

READY_LABELS = frozenset({"ready-for-agent", "ai:ready"})


def pick_one_labeled(
    issues: list[dict], *, occupied: set[int] | None = None
) -> dict:
    """Return ``{ok, issue, reason}`` for at most one labeled, free issue.

    ``issues`` is the caller's list for one repo. Occupancy is the set of
    issue numbers already owned. The first labeled and free issue wins, so
    the caller orders the list.
    """
    taken = occupied or set()
    for issue in issues:
        labels = set(issue.get("labels") or [])
        if not labels & READY_LABELS:
            continue
        number = issue.get("number")
        if number in taken:
            return {"ok": True, "issue": None, "reason": "occupied"}
        return {"ok": True, "issue": issue, "reason": "picked"}
    return {"ok": True, "issue": None, "reason": "none_ready"}
