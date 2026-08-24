"""Apply the shared physical health stop policy to one stabilized pass."""

from lokay.passkit.health import evaluate_mill_stop


def decide(prepared: dict, observed: dict) -> dict:
    route = str(observed.get("route") or "")
    if route in {"idle", "dry", "budget"}:
        return {**observed, "stop_route": route}
    decision = evaluate_mill_stop(observed["tick"])
    return {
        **observed,
        "stop_route": (
            "hard"
            if decision["stop"] and decision["hard"]
            else "soft" if decision["stop"] else "continue"
        ),
        "decision": decision,
    }
