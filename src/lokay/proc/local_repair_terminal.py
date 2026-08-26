"""Lift the closed local-repair result for the parent delivery node."""


def terminal(selected: dict, recheck: dict) -> dict:
    if selected.get("route") == "repaired" and recheck.get("route") == "pass":
        route = "pass"
    elif selected.get("route") == "repaired":
        route = "fail"
    else:
        route = str(selected.get("route") or "terminal")
    payload = {
        "ok": True,
        "route": route,
        "reason": selected.get("reason") or recheck.get("reason"),
        "decision": dict(selected.get("decision") or {}),
        "passed": route == "pass",
    }
    return {**payload, "result": dict(payload)}
