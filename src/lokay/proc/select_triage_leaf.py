"""Route finalized issue triage to an apply leaf or outer-sieve handoff."""

from __future__ import annotations

_ROUTES = frozenset({"ready", "skip", "blocked", "close", "park", "split"})


def select(*, final: dict) -> dict:
    """Select an apply leaf; pass a valid split verdict to the outer issue sieve."""
    decision = dict((final or {}).get("decision") or {})
    verdict = str(decision.get("verdict") or "").strip().lower()
    if verdict not in _ROUTES:
        return {
            "ok": True,
            "route": "fail",
            "reason": "unknown_triage_verdict",
            "verdict": verdict or "missing",
            "decision": decision,
        }
    return {
        "ok": True,
        "route": verdict,
        "reason": str(decision.get("reason") or verdict),
        "decision": decision,
    }
