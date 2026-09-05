"""Build one bounded deterministic issue-split plan."""

from __future__ import annotations
from lokay.models import Issue
from lokay.split import plan_split, validate_split_plan


def plan(*, issue_data: dict, reason: str) -> dict:
    value = plan_split(Issue.from_dict(issue_data), reason=reason or "agent_split")
    if value is None:
        return {
            "ok": True,
            "route": "needs_human",
            "reason": "split_impossible",
            "decision": {"verdict": "needs_human", "reason": "split_impossible"},
            "child_count": 0,
        }
    data = value.to_dict()
    data["parent"] = f"{issue_data['repo']}#{issue_data['number']}"
    validation = validate_split_plan(data, parent=Issue.from_dict(issue_data))
    if not validation["valid"]:
        return {"ok": False, "route": "needs_human", "reason": validation["reason"], "child_count": 0}
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
