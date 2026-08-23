"""Create exactly one indexed child from an authored split plan."""

from __future__ import annotations
from lokay.gh_issues import create_issue


def create(*, runner, repo: str, plan: dict, slot: int, live: bool) -> dict:
    children = list(plan.get("children") or [])
    index = int(slot) - 1
    if index >= len(children):
        return {"ok": True, "route": "absent", "slot": slot}
    child = dict(children[index])
    if not live:
        return {
            "ok": True,
            "route": "created",
            "planned": True,
            "slot": slot,
            "child": child,
        }
    created = create_issue(
        runner,
        repo=repo,
        title=str(child.get("title") or ""),
        body=str(child.get("body") or ""),
        labels=[],
        live=True,
    )
    return {
        "ok": True,
        "route": "created",
        "applied": True,
        "slot": slot,
        "child": {**child, **created},
    }
