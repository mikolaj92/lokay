"""Select one authored serial executor slot. One empty row stops the pass."""


def select(prepared: dict, previous: dict, *, slot: int) -> dict:
    if not prepared.get("ok"):
        return {"ok": True, "route": "empty", "slot": slot}
    remaining = int(prepared.get("budget") or 0)
    slots = int(prepared.get("slot_count") or 0)
    if slot == 1:
        if remaining == 0:
            return {"ok": True, "route": "empty", "slot": slot}
        return {"ok": True, "route": "run", "slot": slot}
    if slots and slot > slots:
        return {"ok": True, "route": "empty", "slot": slot}
    if previous.get("route") != "continue" or not previous.get("launched"):
        return {"ok": True, "route": "empty", "slot": slot}
    return {"ok": True, "route": "run", "slot": slot}
