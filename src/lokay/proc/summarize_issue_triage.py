"""Return the authored issue-triage terminal envelope."""


def summarize(
    *, final: dict, ready: dict, blocked: dict, close: dict, split: dict, manual: dict
) -> dict:
    decision = dict(final.get("decision") or {})
    verdict = str(decision.get("verdict") or "")
    effects = (ready, blocked, close, split, manual)
    applied = any(x.get("applied") is True for x in effects)
    return {
        "ok": True,
        "result": {
            "decision": decision,
            "applied": applied,
            "skipped": verdict in {"skip", "blocked"},
            "implementable": verdict == "ready",
            "split": split,
            "reason": decision.get("reason"),
        },
    }
