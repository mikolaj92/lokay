"""Translate a stopped host gate into receipt fields before persistence."""


def stopped(gate: dict) -> dict:
    route = gate.get("route")
    if route not in {"blocked", "restart"}:
        return {}
    updated = route == "restart"
    return {
        "ok": updated, "health": "host_updated" if updated else "host_behind",
        "reason": gate.get("reason") or ("host_updated" if updated else "host_behind"),
        "error": gate.get("error"), "restart_required": updated,
        "idle": False, "progress": 0, "outcome": "none", "lane": "idle",
    }
