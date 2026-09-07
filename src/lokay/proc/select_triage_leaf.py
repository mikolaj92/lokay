"""Admit which issue-triage apply leaf runs — explicit ok|fail route."""

from __future__ import annotations

_LEAVES = frozenset({"ready", "skip", "blocked", "close", "park"})


def select(*, final: dict) -> dict:
    """Route finalize decision to one apply leaf, or fail unknown verdicts."""
    decision = dict((final or {}).get("decision") or {})
    verdict = str(decision.get("verdict") or "").strip().lower()
    if verdict not in _LEAVES:
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
