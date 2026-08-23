"""Select one authored ready-survey repository slot."""


def select(prepared: dict, *, slot: int) -> dict:
    repos = list(prepared.get("repos") or [])
    if slot < 1 or slot > len(repos):
        return {"ok": True, "route": "empty", "slot": slot}
    repo = str(repos[slot - 1])
    active = set(prepared.get("active_repos") or [])
    return {
        "ok": True,
        "route": "survey" if repo in active else "cold",
        "slot": slot,
        "repo": repo,
    }
