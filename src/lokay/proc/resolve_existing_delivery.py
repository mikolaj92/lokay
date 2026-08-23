"""Reduce physical issue and delivery evidence to one direct Fala route."""

from __future__ import annotations


def resolve(issue: dict, existing: dict, resumed: dict) -> dict:
    if str(issue.get("route")) == "closed":
        return {"ok": True, "route": "no_effect", "reason": "issue_closed"}
    if existing.get("existing_delivery"):
        return {"ok": True, "route": "closeout", "pr": existing["existing_delivery"]}
    if resumed.get("resumed_source"):
        return {"ok": True, "route": "no_effect", "reason": "head_has_on_goal_src"}
    return {"ok": True, "route": "deliver"}
