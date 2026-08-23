"""Purely authorize one bounded PR repair attempt."""


def authorize(gate: dict, source: dict) -> dict:
    item = gate["inspected"]
    allowed = (
        source.get("route") == "repair"
        and bool(item.get("head"))
        and int(item.get("repair_budget") or 0) > 0
        and bool((item.get("policy") or {}).get("executor_enabled"))
    )
    return {
        "ok": True,
        "route": "repair" if allowed else "skip",
        "review": dict(source.get("review") or {}),
        "step": str(source.get("step") or "pr_repair"),
    }
