"""Stabilize an optional repository fragment into one reaction."""


def record(selected: dict, fragment: dict) -> dict:
    return (
        dict(fragment)
        if selected.get("route") == "repo"
        else {"ok": True, "route": "empty", "slot": selected.get("slot")}
    )
