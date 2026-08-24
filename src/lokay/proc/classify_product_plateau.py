"""Purely classify unchanged work as waiting or plateau."""


def _in_flight(remaining):
    return isinstance(remaining, dict) and (
        int(remaining.get("issue_to_pr_started") or 0) > 0
        or any(
            isinstance(x, dict) and x.get("occupied")
            for x in remaining.get("by_repo") or []
        )
    )


def classify(observed: dict) -> dict:
    if observed.get("route") != "compare":
        return {**observed, "route": observed.get("route") or "decide"}
    tick = dict(observed["tick"])
    if _in_flight(tick.get("remaining")) and tick.get("health") in {
        "progress",
        "running",
        "waiting",
    }:
        tick.update(health="waiting", progress=0)
    elif not _in_flight(tick.get("remaining")):
        tick["health"] = "plateau"
    return {**observed, "route": "decide", "tick": tick}
