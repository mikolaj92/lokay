"""Record one physical factory-pass observation in the bounded budget."""


def _key(remaining):
    if not isinstance(remaining, dict):
        return [-1]
    return [
        int(remaining.get(k) or 0)
        for k in (
            "inbox",
            "ready",
            "open_ai_prs",
            "mergeable_green",
            "merge_disabled",
            "needs_repair",
            "no_checks_blocked",
            "merge_conflicts",
            "survey_errors",
        )
    ]


def record(selected: dict, applied: dict, previous: dict) -> dict:
    tick = dict(applied.get("tick") or {})
    slot = int(selected["slot"])
    results = list(previous.get("results") or [])
    results.append(
        {
            "pass": slot,
            "ok": tick.get("ok"),
            "health": tick.get("health"),
            "idle": tick.get("idle"),
            "progress": tick.get("progress"),
            "remaining": tick.get("remaining"),
            "error": tick.get("error"),
        }
    )
    return {
        "ok": True,
        "slot": slot,
        "tick": tick,
        "results": results,
        "total_progress": int(previous.get("total_progress") or 0)
        + int(tick.get("progress") or 0),
        "work_key": _key(tick.get("remaining")),
        "previous_key": previous.get("work_key"),
    }
