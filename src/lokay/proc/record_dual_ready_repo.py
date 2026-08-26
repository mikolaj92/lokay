"""Materialize one dual-ready probe reaction."""


def record(selected: dict, classified: dict) -> dict:
    return {
        "ok": True,
        "slot": selected.get("slot"),
        "repo": str(selected.get("repo") or classified.get("repo") or ""),
        "route": classified.get("route") or selected.get("route") or "empty",
        "issues": list(classified.get("issues") or []),
    }
