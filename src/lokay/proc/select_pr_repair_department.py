"""Authorize the factory-level PR-repair department after the PR sieve."""

from __future__ import annotations

from typing import Any, Mapping

from lokay.envelope import ok


def select(
    triage_run: Mapping[str, Any],
    *,
    enabled: bool,
    triage_ran: bool,
) -> dict[str, Any]:
    if not enabled:
        return ok(route="skip", reason="pr_repair_disabled")
    payload = dict(triage_run or {})
    nested = payload.get("result")
    if isinstance(nested, Mapping):
        payload = {**payload, **dict(nested)}
    triage = payload.get("triage")
    verdict = triage if isinstance(triage, Mapping) else {}
    if str(payload.get("verdict") or "") == "repair":
        verdict = {**verdict, "repairable": True}
    if not verdict.get("repairable"):
        return ok(
            route="skip",
            reason="no_triage_verdict" if triage_ran else "no_triage_verdict",
        )
    return ok(
        route="repair",
        reason=str(verdict.get("reason") or "pr_triage_requested_repair"),
        repo=str(payload.get("repo") or ""),
        pr=int(payload.get("pr") or 0),
        branch=str(payload.get("branch") or ""),
        review=dict(verdict.get("review") or payload.get("review") or {}),
    )
