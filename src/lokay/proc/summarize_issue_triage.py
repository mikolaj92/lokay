"""Return the authored issue-triage terminal envelope."""


def summarize(
    *, final: dict, ready: dict, skip: dict, blocked: dict, close: dict, manual: dict
) -> dict:
    decision = dict(final.get("decision") or {})
    verdict = str(decision.get("verdict") or "")
    effects = (ready, skip, blocked, close, manual)
    applied = any(x.get("applied") is True for x in effects)
    return {
        "ok": True,
        "result": {
            "decision": decision,
            "applied": applied,
            "skipped": verdict in {"skip", "blocked"} or skip.get("skipped") is True,
            "implementable": verdict == "ready",
            "reason": decision.get("reason"),
        },
    }
