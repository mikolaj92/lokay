"""Create exactly one indexed child from an authored split plan."""

from __future__ import annotations
from lokay.gh_issues import create_issue
from lokay.models import Issue
from lokay.split import stable_child_marker


def create(*, runner, repo: str, plan: dict, slot: int, live: bool) -> dict:
    children = list(plan.get("children") or [])
    index = int(slot) - 1
    if index >= len(children):
        return {"ok": True, "route": "absent", "slot": slot}
    child = dict(children[index])
    parent_ref = str(plan.get("parent") or "")
    if "#" in parent_ref:
        parent_repo, parent_number = parent_ref.rsplit("#", 1)
        marker = stable_child_marker(Issue(number=int(parent_number), title="", body="", labels=[], assignees=[], state="OPEN", url="", repo=parent_repo), slot)
    else:
        marker = f"<!-- lokay-split:{repo}:child:{slot} -->"
    child["body"] = str(child.get("body") or "") + "\n" + marker + "\n"
    child["marker"] = marker
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
