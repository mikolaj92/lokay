"""Select one authored leftover-closeout repository slot."""


def select(prepared: dict, *, slot: int) -> dict:
    rows = list(prepared.get("repos") or [])
    if prepared.get("route") != "probe" or slot < 1 or slot > len(rows):
        return {"ok": True, "route": "empty", "slot": slot}
    return {
        "ok": True,
        "route": "labels",
        "slot": slot,
        "repo": rows[slot - 1],
        "labels": list(prepared.get("labels") or []),
    }
