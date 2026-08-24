"""Build one closed terminal payload or continue result for an authored slot."""

from lokay.envelope import err, ok


def finalize(prepared: dict, decided: dict) -> dict:
    route = decided["stop_route"]
    if route == "continue":
        return {**decided, "route": "continue"}
    tick = decided["tick"]
    common = dict(
        mode=prepared["mode"],
        live=prepared["live"],
        passes=decided["slot"],
        max_passes=prepared["budget"],
        progress=decided["total_progress"],
        results=decided["results"],
    )
    if route == "idle":
        payload = ok(**common, idle=True, health="idle", last=tick)
    elif route in {"dry", "budget"}:
        payload = {**tick, **common, "mill": True}
    else:
        decision = decided["decision"]
        common.update(
            idle=False,
            health=decision["health"],
            last=tick,
            remaining=tick.get("remaining"),
        )
        payload = err(decision["error"], **common) if route == "hard" else ok(**common)
    return {**decided, "route": "terminal", "payload": payload}
