"""Purely classify immediate idle, dry-run, comparison, or budget terminal."""


def classify(prepared: dict, recorded: dict) -> dict:
    tick = recorded["tick"]
    slot = recorded["slot"]
    if tick.get("idle") or tick.get("health") == "idle":
        route = "idle"
    elif not prepared.get("live"):
        route = "dry"
    elif recorded.get("previous_key") is not None and tuple(
        recorded["work_key"]
    ) == tuple(recorded["previous_key"]):
        route = "compare"
    elif slot >= prepared["budget"]:
        route = "budget"
    else:
        route = "decide"
    return {**recorded, "route": route}
