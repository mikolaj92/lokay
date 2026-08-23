"""Closed schema and bounded selectors for semantic queue hygiene."""

from lokay.pr_review import extract_json_object, PrReviewError

OUTCOMES = frozenset({"ready", "skip", "close", "needs_human"})


def validate(stdout: str) -> dict:
    try:
        data = extract_json_object(stdout)
        outcome = str(data.get("outcome") or "").strip().lower()
        if outcome not in OUTCOMES:
            raise ValueError(f"outcome must be one of {sorted(OUTCOMES)}")
        reason = str(data.get("reason") or "").strip()
        if not reason:
            raise ValueError("reason must be a non-empty string")
        if "detail" in data and not isinstance(data["detail"], dict):
            raise ValueError("detail must be an object")
        if "add_tracker" in data and not isinstance(data["add_tracker"], bool):
            raise ValueError("add_tracker must be a boolean")
        return {
            "ok": True,
            "route": "valid",
            "decision": {
                "outcome": outcome,
                "reason": reason,
                "detail": dict(data.get("detail") or {}),
                "summary": str(data.get("summary") or "").strip(),
                "add_tracker": bool(data.get("add_tracker", False)),
            },
        }
    except (ValueError, PrReviewError) as exc:
        return {
            "ok": True,
            "route": "retry",
            "validation_error": str(exc),
            "agent_stdout_tail": stdout[-2000:],
        }


def select(target: dict, covering: dict, first: dict, retry: dict) -> dict:
    if target.get("route") == "none":
        return {"ok": True, "route": "none", "reason": target.get("reason")}
    if covering.get("route") == "covered":
        decision = dict(covering["decision"])
    elif first.get("route") == "valid":
        decision = dict(first["decision"])
    elif retry.get("route") == "valid":
        decision = dict(retry["decision"])
    else:
        decision = {
            "outcome": "needs_human",
            "reason": "invalid_queue_conflict_json",
            "detail": {},
            "summary": "Queue conflict agent did not return valid JSON.",
            "add_tracker": False,
        }
    return {
        "ok": True,
        "route": decision["outcome"],
        "decision": decision,
        "repo": covering.get("repo"),
        "issue": covering.get("issue"),
        "candidate": covering.get("candidate"),
    }
