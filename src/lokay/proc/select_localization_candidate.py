"""Purely select the candidate authored by the localization route."""


def select(
    route: dict,
    explicit: dict,
    fallback: dict,
    first: dict,
    retry: dict,
    first_attempt: dict,
    retry_attempt: dict,
) -> dict:
    chosen = str(route.get("route") or "terminal")
    if chosen in {"existing", "explicit"}:
        return {**explicit, "ok": True}
    if chosen == "fallback":
        return {**fallback, "ok": True}
    if chosen == "terminal":
        return {"ok": True, "route": "terminal", "reason": "empty_seed", "paths": []}
    if first.get("route") == "valid":
        return {
            "ok": True,
            "route": "candidate",
            "paths": first["paths"],
            "source": "agent",
            "notes": [],
        }
    if retry.get("route") == "valid":
        return {
            "ok": True,
            "route": "candidate",
            "paths": retry["paths"],
            "source": "agent",
            "notes": [],
        }
    if (
        first_attempt.get("route") == "fallback"
        or retry_attempt.get("route") == "fallback"
    ):
        return {**fallback, "ok": True}
    return {"ok": True, "route": "terminal", "reason": "invalid_json", "paths": []}
