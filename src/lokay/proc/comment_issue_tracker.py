"""Publish the one parent-tracker child reference comment."""

from __future__ import annotations
from lokay.gh_issues import comment_issue
from lokay.split import ChildSpec, SplitPlan, parent_tracker_comment


def apply(
    *, runner, repo: str, issue: int, plan_data: dict, children: list[dict], live: bool
) -> dict:
    numbers = [int(x["number"]) for x in children if x.get("number")]
    if not live:
        return {"ok": True, "planned": True, "children": children}
    specs = tuple(ChildSpec(**x) for x in plan_data.get("children") or [])
    plan = SplitPlan(reason=str(plan_data.get("reason") or "split"), children=specs)
    comment_issue(runner, repo, issue, parent_tracker_comment(plan, numbers), live=True)
    return {"ok": True, "applied": True, "children": children}
