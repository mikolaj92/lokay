"""Purely route one full declared test result."""


def select(executed: dict, *, changed_scope: bool) -> dict:
    if executed.get("route") == "green":
        route = "cache"
    elif executed.get("route") == "red" and changed_scope:
        route = "scope"
    else:
        route = "terminal"
    return {**executed, "ok": True, "route": route}
