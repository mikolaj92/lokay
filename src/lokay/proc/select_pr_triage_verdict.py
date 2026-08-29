"""Map a PR sieve result to merge / feedback / repair. Does not start repair."""

from __future__ import annotations

from typing import Any, Mapping

from lokay.envelope import ok


def classify(triage_run: Mapping[str, Any]) -> dict:
    """First block: read the child pr_triage envelope."""
    triage = triage_run.get("triage")
    blob = triage if isinstance(triage, Mapping) else triage_run
    return {
        "repairable": bool(blob.get("repairable")),
        "merged": bool(blob.get("merged")),
        "waiting": bool(blob.get("waiting")),
        "reason": str(blob.get("reason") or triage_run.get("reason") or ""),
        "review": dict(blob.get("review") or {}),
    }


def select(picked: Mapping[str, Any], triage_run: Mapping[str, Any]) -> dict:
    """Second block: verdict only. repair does not invoke pr_repair."""
    if str(picked.get("route") or "") != "pr":
        return ok(route="skip", verdict="none", reason=str(picked.get("reason") or "no_open_pr"))
    facts = classify(triage_run)
    if facts["merged"]:
        verdict = "merge"
    elif facts["repairable"]:
        verdict = "repair"
    elif facts["waiting"]:
        verdict = "feedback"
    else:
        verdict = "feedback"
    return ok(
        route="completed",
        verdict=verdict,
        repairable=facts["repairable"],
        merged=facts["merged"],
        waiting=facts["waiting"],
        reason=facts["reason"] or verdict,
        review=facts["review"],
        repo=picked.get("repo"),
        pr=picked.get("pr"),
        branch=picked.get("branch"),
        triage={
            "repairable": facts["repairable"],
            "reason": facts["reason"] or verdict,
            "review": facts["review"],
            "merged": facts["merged"],
            "waiting": facts["waiting"],
        },
    )
