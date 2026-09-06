"""Purely select existing, explicit, deterministic, or terminal localization route.

Happy path before coding uses deterministic structure/grep (#1032). Semantic
localize agent is not a second LLM call ahead of run_agent.
"""


def classify(request: dict, inspected: dict, *, agent_allowed: bool) -> dict:
    del agent_allowed  # kept for call-site compat; never prefers agent (#1032)
    if inspected.get("existing"):
        route = "existing"
    elif request.get("has_file_hints"):
        route = "explicit"
    elif not str(request.get("seed") or "").strip():
        route = "terminal"
    else:
        route = "fallback"
    return {"ok": True, "route": route}
