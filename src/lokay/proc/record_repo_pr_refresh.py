"""Stabilize optional repository PR refresh into one reaction."""


def record(selected: dict, inspected: dict, listed: dict) -> dict:
    if selected.get("route") != "repo":
        return {"ok": True, "route": "empty", "slot": selected.get("slot")}
    return dict(listed if listed.get("ok") else inspected)
