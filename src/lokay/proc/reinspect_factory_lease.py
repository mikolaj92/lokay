"""Recheck the exact delegated capability after one bounded restoration."""

from lokay.preflight import health_lease_status


def inspect(restored: dict) -> dict:
    if restored.get("route") != "inspect":
        return {"ok": True, "route": "unused"}
    healthy, reason = health_lease_status()
    return {
        "ok": True,
        "route": "load" if healthy else "terminal",
        "lease_reason": reason,
    }
