"""Select one authored live-receipt slot."""


def select(prepared: dict, *, slot: int) -> dict:
    rows = list(prepared.get("receipts") or [])
    if slot < 1 or slot > len(rows):
        return {"ok": True, "route": "empty", "slot": slot}
    return {
        "ok": True,
        "route": "receipt",
        "slot": slot,
        "receipt": dict(rows[slot - 1]),
    }
