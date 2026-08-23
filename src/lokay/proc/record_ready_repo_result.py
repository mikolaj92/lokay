"""Materialize one authored ready-survey slot reaction."""


def record(selected: dict, classified: dict, parked: dict) -> dict:
    repo = str(selected.get("repo") or classified.get("repo") or "")
    return {
        "ok": True,
        "slot": selected.get("slot"),
        "repo": repo,
        "route": classified.get("route") or selected.get("route") or "empty",
        "implementable": list(classified.get("implementable") or []),
        "covered": list(classified.get("covered") or []),
        "blocked": list(classified.get("blocked") or []),
        "parked": dict(parked or {}),
    }
