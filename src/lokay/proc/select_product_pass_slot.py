"""Select one authored serial product-pass slot."""


def select(prepared: dict, previous: dict, *, slot: int) -> dict:
    if slot > int(prepared.get("budget") or 0):
        return {"ok": True, "route": "empty", "slot": slot}
    if slot > 1 and previous.get("route") != "continue":
        return {"ok": True, "route": "empty", "slot": slot}
    return {"ok": True, "route": "run", "slot": slot}
