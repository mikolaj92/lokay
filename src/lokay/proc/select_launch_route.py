"""Stabilize the optional detached-launch branch for direct downstream conditions."""


def select(ready: dict, launch: dict) -> dict:
    if ready.get("route") != "ready":
        return {"ok": True, "route": "none"}
    return {"ok": True, **ready, **launch, "route": launch.get("route") or "failed"}
