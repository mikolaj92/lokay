"""Stabilize optional full/scoped green test results for cache writing."""


def select(full: dict, scoped: dict) -> dict:
    if scoped.get("route") == "green":
        return {"ok": True, "route": "green", "source": scoped}
    if full.get("route") == "green":
        return {"ok": True, "route": "green", "source": full}
    return {"ok": True, "route": "none", "source": {}}
