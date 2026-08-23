"""Select one authored repository slot for stale-stage recovery."""


def select(prepared: dict, *, slot: int) -> dict:
    repos = list(prepared.get("repos") or [])
    if prepared.get("route") != "probe" or slot < 1 or slot > len(repos):
        return {"ok": True, "route": "empty", "slot": slot}
    repo = str(repos[slot - 1])
    scope = prepared.get("scope")
    return {
        "ok": True,
        "route": "repo" if scope is None or repo in set(scope) else "outside_scope",
        "slot": slot,
        "repo": repo,
    }
