"""Purely classify self-repair entry preconditions."""


def classify(prepared: dict) -> dict:
    failed = set(prepared.get("failed_names") or [])
    if not prepared.get("carrier_ok"):
        reason = "carrier_unhealthy"
    elif prepared.get("issue") is None or not prepared.get("fingerprint"):
        reason = "deduplicated_incident_unavailable"
    elif failed & {"github_authentication", "executor_availability"}:
        reason = "bootstrap_dependency_unavailable"
    elif not prepared.get("executor_enabled"):
        reason = "executor_disabled"
    else:
        return {"ok": True, "route": "run", "reason": ""}
    return {"ok": True, "route": "terminal", "reason": reason}
