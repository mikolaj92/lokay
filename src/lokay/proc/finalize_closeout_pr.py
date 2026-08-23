"""Reduce one authored PR-closeout path into a closed result envelope."""

from lokay.closeout import COUNTERS, apply_deltas, pr_envelope


def finalize(
    gate: dict, checks_route: dict, triage_route: dict, repair: dict, evidence: dict
) -> dict:
    item = gate["inspected"]
    route = str(gate.get("route") or "")
    if route == "checks":
        route = str(checks_route.get("domain_route") or "skip")
    reason = str(
        gate.get("reason")
        or checks_route.get("reason")
        or triage_route.get("reason")
        or ""
    )
    if route in {"issue_closed", "manual", "conflict"}:
        route = "skip"
    merged = triage_route.get("route") == "merged"
    c = {k: 0 for k in COUNTERS}
    apply_deltas(c, checks_route.get("deltas") or {})
    apply_deltas(c, triage_route.get("deltas") or {})
    out = pr_envelope(
        repo=item["repo"],
        pr=item["pr_number"],
        route="merge" if merged else route,
        reason=reason,
        still_open=not merged,
        actions=list(evidence.get("actions") or []),
        repair_budget=max(
            0, int(item.get("repair_budget") or 0) - int(repair.get("repair_used") or 0)
        ),
        progress=int(merged),
        remaining_closed=int(merged),
        counters=c,
    )
    out["park_manual"] = bool(triage_route.get("park_manual"))
    return out
