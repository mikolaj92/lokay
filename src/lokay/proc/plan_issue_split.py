"""Build one bounded deterministic issue-split plan."""

from __future__ import annotations

from lokay.models import Issue
from lokay.proc._prose_agent import ask
from lokay.split import plan_from_agent, validate_split_plan

_PROMPT = """Read the issue. Reply with one JSON object and nothing else:
{{"children": [{{"title": "one slice", "detail": "what this slice changes"}}]}}
Split only when the issue is several pieces of work. One piece means {{"children": []}}.

Issue #{number} — {title}

{body}
"""


def plan(*, issue_data: dict, reason: str, execute=None) -> dict:
    split_reason = reason or "agent_split"
    item = Issue.from_dict(issue_data)
    prompt = _PROMPT.format(number=item.number, title=item.title or "", body=item.body or "")
    agent = ask(item, issue_data, prompt, execute)
    value = plan_from_agent(item, agent or {}, reason=split_reason)
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
