"""Materialize durable action evidence from optional one-PR effects."""


def build(gate: dict, checks: dict, triage: dict, repair: dict, parked: dict) -> dict:
    item = gate["inspected"]
    actions = []
    sources = (
        ("get_issue", gate.get("issue_read", {}).get("read")),
        ("pr_checks", checks.get("checks")),
        ("pr_triage", triage.get("triage")),
        (repair.get("step") or "pr_repair", repair.get("repair")),
        ("park_closed_issue", parked.get("parked")),
    )
    for step, data in sources:
        if data:
            actions.append(
                {
                    "step": step,
                    "repo": item["repo"],
                    "pr": item["pr_number"],
                    **dict(data),
                }
            )
    return {"ok": True, "actions": actions}
