"""Select one authored stale-stage candidate slot."""


def select(probe: dict, gate: dict, *, slot: int) -> dict:
    rows = list(probe.get("candidates") or [])
    if slot < 1 or slot > len(rows):
        return {"ok": True, "route": "empty", "slot": slot}
    return {
        "ok": True,
        "route": "apply" if gate.get("apply") else "plan",
        "slot": slot,
        **dict(rows[slot - 1]),
    }
