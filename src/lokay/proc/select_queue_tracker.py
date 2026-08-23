"""Stabilize optional tracker mutation into one closed route."""


def select(outcome: dict) -> dict:
    route = (
        "tracker"
        if outcome.get("route") == "close"
        and bool((outcome.get("decision") or {}).get("add_tracker"))
        else "none"
    )
    return {
        "ok": True,
        "route": route,
        **{key: outcome.get(key) for key in ("repo", "issue", "decision")},
    }
