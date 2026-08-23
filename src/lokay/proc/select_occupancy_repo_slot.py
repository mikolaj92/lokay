"""Select one authored occupancy repository slot."""


def select(prepared: dict, *, slot: int) -> dict:
    repos = list(prepared.get("repos") or [])
    if slot < 1 or slot > len(repos):
        return {"ok": True, "route": "empty", "slot": slot}
    return {"ok": True, "route": "repo", "slot": slot, "repo": str(repos[slot - 1])}
