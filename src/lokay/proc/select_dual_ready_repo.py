"""Select one authored dual-ready probe slot (cold repos only)."""


def select(prepared: dict, *, slot: int) -> dict:
    repos = list(prepared.get("repos") or [])
    if slot < 1 or slot > len(repos):
        return {"ok": True, "route": "empty", "slot": slot}
    repo = str(repos[slot - 1])
    if prepared.get("recent_empty") or prepared.get("route") == "skip":
        return {"ok": True, "route": "empty", "slot": slot, "repo": repo}
    active = {str(name) for name in prepared.get("active_repos") or []}
    return {
        "ok": True,
        "route": "skip" if repo in active else "probe",
        "slot": slot,
        "repo": repo,
        "labels": list(prepared.get("labels") or ["work:ready", "ai:ready"]),
    }
