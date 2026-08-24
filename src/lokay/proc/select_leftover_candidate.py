"""Select one authored CLOSED ready issue candidate."""


def select(reduced: dict, *, slot: int) -> dict:
    rows = list(reduced.get("candidates") or [])
    if reduced.get("route") != "mutate" or slot < 1 or slot > len(rows):
        return {"ok": True, "route": "empty", "slot": slot}
    return {
        "ok": True,
        "route": "park",
        "slot": slot,
        **rows[slot - 1],
        "mutations_allowed": bool(reduced.get("mutations_allowed")),
    }
