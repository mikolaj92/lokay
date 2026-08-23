"""Fala bindings for bounded issue-split physical effects."""

from __future__ import annotations
from typing import Any
from lokay.config import load_config
from lokay.proc._common import mutations_allowed, runner

OWNED = frozenset(
    {
        "plan_issue_split",
        "create_issue_split_child_1",
        "create_issue_split_child_2",
        "create_issue_split_child_3",
        "create_issue_split_child_4",
        "create_issue_split_child_5",
        "mark_issue_tracker",
        "comment_issue_tracker",
        "close_issue_tracker",
        "summarize_issue_split",
    }
)


def handle_issue_split(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    if atom not in OWNED:
        return None
    repo, number, live = str(ctx["repo"]), int(ctx["issue_number"]), bool(ctx["live"])
    cfg = load_config(str(inputs.get("config_path") or "") or None)
    mutate = mutations_allowed(live_flag=live, cfg=cfg)
    issue = dict((up.get("get_issue") or {}).get("issue") or {})
    if atom == "plan_issue_split":
        from lokay.proc.plan_issue_split import plan

        decision = dict((up.get("finalize_issue_triage") or {}).get("decision") or {})
        if not decision and inputs.get("split_reason"):
            decision = {"verdict": "split", "reason": str(inputs["split_reason"])}
        if decision.get("verdict") != "split":
            return {
                "ok": True,
                "route": "not_applicable",
                "child_1": "absent",
                "child_2": "absent",
                "child_3": "absent",
                "child_4": "absent",
                "child_5": "absent",
            }
        return plan(
            issue_data=issue, reason=str(decision.get("reason") or "agent_split")
        )
    if atom.startswith("create_issue_split_child_"):
        from lokay.proc.create_issue_split_child import create

        return create(
            runner=runner(),
            repo=repo,
            plan=dict((up.get("plan_issue_split") or {}).get("plan") or {}),
            slot=int(atom.rsplit("_", 1)[1]),
            live=mutate,
        )
    plan_data = dict((up.get("plan_issue_split") or {}).get("plan") or {})
    if atom == "summarize_issue_split":
        from lokay.proc.summarize_issue_split import summarize

        return summarize(
            plan=up.get("plan_issue_split") or {},
            comment=up.get("comment_issue_tracker") or {},
            close=up.get("close_issue_tracker") or {},
            manual=up.get("apply_issue_manual") or {},
        )
    if atom == "mark_issue_tracker":
        from lokay.proc.mark_issue_tracker import apply

        return apply(
            runner=runner(),
            cfg=cfg,
            repo=repo,
            issue=number,
            issue_data=issue,
            plan=plan_data,
            live=mutate,
        )
    if atom == "comment_issue_tracker":
        from lokay.proc.comment_issue_tracker import apply

        children = [
            dict((up.get(f"create_issue_split_child_{slot}") or {}).get("child") or {})
            for slot in range(1, 6)
        ]
        children = [x for x in children if x]
        return apply(
            runner=runner(),
            repo=repo,
            issue=number,
            plan_data=plan_data,
            children=children,
            live=mutate,
        )
    if atom == "close_issue_tracker":
        from lokay.proc.close_issue_tracker import apply

        return apply(runner=runner(), repo=repo, issue=number, live=mutate)
    return None
