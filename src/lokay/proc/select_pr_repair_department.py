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
    if triage_ran:
        return ok(route="skip", reason="already_conducted_in_pr_triage")
    triage = triage_run.get("triage")
    verdict = triage if isinstance(triage, Mapping) else {}
    if not verdict.get("repairable"):
        return ok(route="skip", reason="no_triage_verdict")
    return ok(
        route="repair",
        reason=str(verdict.get("reason") or "pr_triage_requested_repair"),
        repo=str(triage_run.get("repo") or ""),
        pr=int(triage_run.get("pr") or 0),
        branch=str(triage_run.get("branch") or ""),
    )
