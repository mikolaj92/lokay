"""Stabilize performed, skipped, or failed recovery fast-forward."""


def record(fetch: dict, merged: dict) -> dict:
    if merged.get("route"):
        return merged
    return {
        "ok": True,
        "route": "unused" if fetch.get("route") != "fetched" else "terminal",
        "reason": "" if fetch.get("route") != "fetched" else "fast_forward_failed",
    }
