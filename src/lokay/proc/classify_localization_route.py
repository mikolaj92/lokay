def classify(request: dict, inspected: dict, *, agent_allowed: bool) -> dict:
    seed = str(request.get("seed") or "").strip()
    if inspected.get("existing"):
        route = "existing"
    elif not seed:
        route = "terminal"
    elif agent_allowed:
        route = "agent"
    elif request.get("has_file_hints"):
        route = "explicit"
    else:
        route = "fallback"
    return {"ok": True, "route": route}
