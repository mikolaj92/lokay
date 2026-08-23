"""Select the optional plan-only park edge after blocked-state persistence."""


def select(blocked: dict, outcome: dict) -> dict:
    if outcome.get("route") != "blocked":
        return {"ok": True, "route": "done"}
    return {"ok": True, "route": blocked.get("route") or "done", **blocked}
