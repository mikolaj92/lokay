"""Stabilize the optional stuck-ledger gate for direct Fala routing."""


def select(target: dict, gate: dict) -> dict:
    if target.get("route") != "target":
        return {"ok": True, "route": "none"}
    return {"ok": True, **target, **gate, "route": gate.get("route") or "blocked"}
