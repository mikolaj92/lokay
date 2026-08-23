"""Stabilize the optional mutex branch for direct downstream Fala conditions."""


def select(candidate: dict, mutex: dict) -> dict:
    if candidate.get("route") != "candidate":
        return {"ok": True, "route": "none"}
    return {"ok": True, **candidate, **mutex, "route": mutex.get("route") or "keep"}
