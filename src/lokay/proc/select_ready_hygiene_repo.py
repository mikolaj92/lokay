"""Select one authored ready-hygiene repository slot."""


def select(prepared: dict, *, slot: int) -> dict:
    repos = list(prepared.get("repos") or [])
    if prepared.get("route") == "skip" or slot < 1 or slot > len(repos):
        return {"ok": True, "route": "empty", "slot": slot}
    return {
        "ok": True,
        "route": "probe",
        "slot": slot,
        "repo": repos[slot - 1],
        "ready_label": prepared["ready_label"],
    }
