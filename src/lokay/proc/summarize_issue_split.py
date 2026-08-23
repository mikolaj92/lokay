"""Return the authored issue-split terminal envelope."""


def summarize(*, plan: dict, comment: dict, close: dict, manual: dict) -> dict:
    children = list(comment.get("children") or [])
    route = str(plan.get("route") or "")
    decision = {
        "verdict": "split" if route == "children" else "needs_human",
        "reason": plan.get("reason"),
    }
    return {
        "ok": True,
        "result": {
            "applied": close.get("applied") is True or manual.get("applied") is True,
            "children": children,
            "plan": plan.get("plan"),
            "decision": decision,
        },
    }
