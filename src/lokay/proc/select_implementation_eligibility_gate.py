"""Stabilize optional repository inspection into one closed route."""


def select(selected: dict, inspected: dict) -> dict:
    if selected.get("route") != "repo":
        return {"ok": True, "route": "empty", "slot": selected.get("slot")}
    return dict(inspected)
