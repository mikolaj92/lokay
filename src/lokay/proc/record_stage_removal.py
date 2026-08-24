"""Stabilize performed, absent, or failed stage-label removal."""


def record(classified: dict, removed: dict) -> dict:
    if removed.get("route"):
        return removed
    return {
        "ok": True,
        "route": "none" if classified.get("route") == "add" else "terminal",
        "reason": classified.get("reason") or "",
    }
