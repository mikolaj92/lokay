"""Sieve verdict only: do / skip / split. Never launch. Zero limbo stamps."""

from __future__ import annotations

from typing import Any, Mapping

from lokay.envelope import ok
from lokay.proc.classify_issue_do import classify
from lokay.proc.select_issue_do import leftover_of
from lokay.proc.walk_issue_leftover import consumes, row_is_ready

_SPLIT_MARKERS = ("split", "issue_split", "multi_epic", "oversized")
_SKIP = frozenset({"close", "blocked", "mark", "park", "skip"})


def classify_sieve(triage_run: Mapping[str, Any], picked: Mapping[str, Any]) -> dict:
    """Map one sito envelope to a sieve route. Zero code. Zero PR."""
    sito = classify(dict(triage_run))
    blob = triage_run.get("triage") if isinstance(triage_run.get("triage"), dict) else {}
    result = blob.get("result") if isinstance(blob.get("result"), dict) else {}
    decision = blob.get("decision") if isinstance(blob.get("decision"), dict) else {}
    if not decision:
        nested = result.get("decision")
        decision = nested if isinstance(nested, dict) else {}
    verdict = str(decision.get("verdict") or result.get("verdict") or "")
    reason = str(
        decision.get("reason") or result.get("reason") or sito.get("reason") or ""
    )
    # Terminal close/blocked/mark win even if reason mentions "split".
    if verdict in {"close", "blocked", "mark"}:
        return ok(
            route="skip",
            reason=reason or verdict,
            verdict="close" if verdict == "close" else "skip",
        )
    if verdict == "ready" or sito.get("route") == "ready":
        return ok(route="do", reason=reason or "ready", verdict="ready")
    token = f"{verdict} {reason}".lower()
    # park/fail_closed with split markers → auto-split (#1014).
    if any(marker in token for marker in _SPLIT_MARKERS):
        return ok(route="split", reason=reason or "issue_split", verdict=verdict)
    if verdict in _SKIP or reason in _SKIP:
        return ok(
            route="skip",
            reason=reason or verdict or "skip",
            verdict="skip",
        )
    if verdict in {"fail_closed", "needs_human", "human", "manual"} or reason in {
        "fail_closed",
        "needs_human",
        "human",
    }:
        return ok(route="skip", reason=reason or "skip", verdict="skip")
    if not consumes(sito.get("reason")) and row_is_ready(dict(picked)):
        return ok(route="do", reason="already_ready", verdict="ready")
    return ok(route="skip", reason=reason or sito.get("reason") or "sito_nie_robic")


def select(
    picked: Mapping[str, Any],
    triage_run: Mapping[str, Any],
    listed: Mapping[str, Any] | None = None,
) -> dict:
    listed_map = dict(listed or {})
    picked_route = str(picked.get("route") or "")
    if picked_route == "ready":
        leftover, leftover_issues = leftover_of(dict(picked), listed_map, consume=True)
        return ok(
            route="do",
            reason="already_ready",
            verdict="ready",
            repo=picked.get("repo"),
            issue=picked.get("issue"),
            leftover=leftover,
            leftover_issues=leftover_issues,
        )
    if picked_route != "issue":
        leftover, leftover_issues = leftover_of(dict(picked), listed_map, consume=False)
        return ok(
            route="skip",
            reason="no_issue",
            leftover=leftover,
            leftover_issues=leftover_issues,
        )
    sieve = classify_sieve(triage_run, picked)
    leftover, leftover_issues = leftover_of(dict(picked), listed_map, consume=True)
    return ok(
        route=sieve["route"],
        reason=sieve.get("reason"),
        verdict=sieve.get("verdict"),
        repo=picked.get("repo"),
        issue=picked.get("issue"),
        leftover=leftover,
        leftover_issues=leftover_issues,
    )
