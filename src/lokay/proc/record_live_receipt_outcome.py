"""Stabilize optional live-receipt effects into one reaction."""


def record(selected: dict, inspected: dict, terminated: dict, cleared: dict) -> dict:
    if selected.get("route") != "receipt":
        return {"ok": True, "route": "empty", "slot": selected.get("slot")}
    if inspected.get("route") not in {"terminated", "keep"}:
        return dict(inspected)
    return {
        **inspected,
        "route": "closed",
        "terminated": bool(terminated.get("terminated")),
        "cleared": bool(cleared.get("cleared")),
    }
