"""Purely select existing, explicit, deterministic, agent, or terminal localization route."""


def classify(request: dict, inspected: dict, *, agent_allowed: bool) -> dict:
    if inspected.get("existing"):
        route = "existing"
    elif request.get("has_file_hints"):
        route = "explicit"
    elif not str(request.get("seed") or "").strip():
        route = "terminal"
    elif agent_allowed and inspected.get("worktree_exists"):
        route = "agent"
    else:
        route = "fallback"
    return {"ok": True, "route": route}
