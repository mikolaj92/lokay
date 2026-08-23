"""Select one authored PR-survey repository slot."""


def select(prepared: dict, *, slot: int) -> dict:
    repos = list(prepared.get("repos") or [])
    if slot < 1 or slot > len(repos):
        return {"ok": True, "route": "empty", "slot": slot}
    repo = str(repos[slot - 1])
    route = (
        "outside_mini"
        if repo in set(prepared.get("skipped_repos") or [])
        else (
            "cold"
            if prepared.get("scoped")
            and repo not in set(prepared.get("active_repos") or [])
            else "recent_empty" if prepared.get("recent_empty") else "survey"
        )
    )
    return {"ok": True, "route": route, "slot": slot, "repo": repo}
