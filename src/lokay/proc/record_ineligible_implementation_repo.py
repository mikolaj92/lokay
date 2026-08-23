"""Record one ineligible implementation repository reaction."""


def record(selected: dict, inspected: dict) -> dict:
    if selected.get("route") != "repo":
        return {"ok": True, "route": "empty", "slot": selected.get("slot")}
    return dict(inspected)
