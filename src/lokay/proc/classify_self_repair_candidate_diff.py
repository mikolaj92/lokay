"""Purely validate that a recovery candidate contains real product changes."""


def classify(state: dict) -> dict:
    if not state.get("changed") and state.get("committed") == "empty":
        return {**state, "ok": False, "error": "self-repair produced zero diff"}
    if state.get("committed") == "plan_only":
        return {
            **state,
            "ok": False,
            "error": "self-repair candidate has committed plan evidence",
        }
    return {**state, "ok": True, "route": "identity"}
