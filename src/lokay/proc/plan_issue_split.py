"""Build one bounded deterministic issue-split plan."""

from __future__ import annotations
from lokay.models import Issue
from lokay.split import plan_split, validate_split_plan


def plan(*, issue_data: dict, reason: str) -> dict:
    split_reason = reason or "agent_split"
    value = plan_split(Issue.from_dict(issue_data), reason=split_reason)
    if value is None:
        # Host-ops monolith without extractable code+ops children → skip (no limbo).
        park_reason = (
            "host_ops" if "host_ops" in split_reason.lower() else "split_impossible"
        )
        return {
            "ok": True,
            "route": "park",
            "reason": park_reason,
            "decision": {"verdict": "park", "reason": park_reason},
            "child_count": 0,
        }
    data = value.to_dict()
    data["parent"] = f"{issue_data['repo']}#{issue_data['number']}"
    validation = validate_split_plan(data, parent=Issue.from_dict(issue_data))
    if not validation["valid"]:
        return {"ok": False, "route": "park", "reason": validation["reason"], "child_count": 0}
    count = len(data["children"])
    slots = {
        f"child_{slot}": "present" if slot <= count else "absent"
        for slot in range(1, 6)
    }
    return {
        "ok": True,
        "route": "children",
        "plan": data,
        "child_count": count,
        "validation": validation,
        **slots,
    }
