"""Inspect the inherited factory health capability without mutating it."""

import os
from lokay.preflight import health_lease_status


def inspect(*, live: bool) -> dict:
    delegated = bool(live and os.environ.get("LOKAY_HEALTH_LEASE"))
    if not delegated:
        return {"ok": True, "route": "preflight", "delegated": False}
    healthy, reason = health_lease_status()
    if healthy:
        return {"ok": True, "route": "load", "delegated": True, "lease_reason": "ok"}
    restorable = (
        str(reason).startswith("lease_unavailable_FileNotFound")
        or str(reason).startswith("lease_unavailable_ProcessLookup")
        or str(reason) == "lock_not_held"
    )
    return {
        "ok": True,
        "route": "restore" if restorable else "terminal",
        "delegated": True,
        "lease_reason": reason,
    }
