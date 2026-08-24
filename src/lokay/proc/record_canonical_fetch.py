"""Stabilize performed, skipped, or failed canonical fetch."""


def record(checkout: dict, fetched: dict) -> dict:
    if fetched.get("route"):
        return fetched
    return {
        "ok": True,
        "route": "unused" if checkout.get("route") != "clean" else "terminal",
        "reason": "" if checkout.get("route") != "clean" else "fetch_failed",
    }
