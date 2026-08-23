"""Stabilize the optional physical-ready branch for direct downstream conditions."""


def select(mutex: dict, ready: dict) -> dict:
    if mutex.get("route") != "free":
        return {"ok": True, "route": "none"}
    return {"ok": True, **mutex, **ready, "route": ready.get("route") or "stale"}
