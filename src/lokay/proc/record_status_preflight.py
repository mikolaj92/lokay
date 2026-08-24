"""Stabilize requested or absent read-only preflight evidence."""


def record(config: dict, preflight: dict) -> dict:
    if preflight.get("route") == "record":
        return preflight
    return {"ok": True, "route": "unused", "preflight": None}
