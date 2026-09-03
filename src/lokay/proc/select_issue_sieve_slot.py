"""Select one authored serial issue-sieve slot."""


def select(prepared: dict, previous: dict, *, slot: int) -> dict:
    if not prepared.get("ok"):
        return {"ok": True, "route": "empty", "slot": slot}
    remaining = int(prepared.get("budget") or 0)
    spent = int(prepared.get("spent") or 0)
    if slot == 1:
        if remaining == 0 and spent > 0:
            return {"ok": True, "route": "empty", "slot": slot}
        return {"ok": True, "route": "run", "slot": slot}
    if slot > remaining:
        return {"ok": True, "route": "empty", "slot": slot}
    if previous.get("route") != "continue":
        return {"ok": True, "route": "empty", "slot": slot}
    return {"ok": True, "route": "run", "slot": slot}
