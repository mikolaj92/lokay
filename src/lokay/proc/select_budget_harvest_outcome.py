"""Stabilize optional commit, push, and PR effects into one harvest outcome."""


def select(route: dict, committed: dict, pushed: dict, created: dict) -> dict:
    if route.get("route") != "harvest":
        return dict(route)
    for row in (created, pushed, committed):
        if row.get("ok"):
            return dict(row)
    return {**route, "route": "keep", "reason": "coder_live"}
