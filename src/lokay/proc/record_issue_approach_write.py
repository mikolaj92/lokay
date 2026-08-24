"""Stabilize written, planned, or failed issue approach evidence."""


def record(authorized: dict, written: dict) -> dict:
    if written.get("route"):
        return written
    return {
        "ok": True,
        "route": "planned" if authorized.get("route") == "planned" else "terminal",
        "reason": authorized.get("reason") or "",
    }
