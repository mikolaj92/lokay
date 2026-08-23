"""Purely route checks and execution policy for one PR."""

from lokay.closeout import route_deltas
from lokay.proc.pr_route import run_pr_route


def route(gate: dict, checked: dict, *, live: bool) -> dict:
    item = gate["inspected"]
    if checked.get("route") != "route":
        return {"ok": True, "route": "final", "reason": "checks_error", "deltas": {}}
    policy = item.get("policy") or {}
    out = run_pr_route(
        checks=checked.get("checks"),
        merge_enabled=bool(policy.get("merge_enabled")),
        require_checks=bool(policy.get("require_checks")),
        labels=(item.get("pr") or {}).get("labels"),
    )
    r = str(out.get("route") or "skip")
    reason = str(out.get("reason") or "")
    route = (
        "repair"
        if r == "repair"
        else "triage" if r == "merge" and live and item.get("head") else "final"
    )
    return {
        "ok": True,
        "route": route,
        "domain_route": r,
        "reason": reason,
        "deltas": route_deltas(r, reason),
        "routed": out,
    }
