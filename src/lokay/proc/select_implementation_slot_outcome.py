"""Stabilize optional eligibility branches into one slot reaction."""


def select(selected: dict, eligible: dict, ineligible: dict) -> dict:
    if selected.get("route") != "repo":
        return {"ok": True, "route": "empty", "slot": selected.get("slot")}
    return dict(eligible or ineligible)
