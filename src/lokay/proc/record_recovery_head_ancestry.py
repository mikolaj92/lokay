"""Stabilize performed or absent recovery HEAD ancestry check."""


def record(classified: dict, checked: dict) -> dict:
    if checked.get("route"):
        return checked
    return {
        "ok": True,
        "route": "unused" if classified.get("route") != "ancestry" else "not_ancestor",
    }
