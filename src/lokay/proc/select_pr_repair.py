"""Authorize the separate PR-repair department after the PR sieve verdict."""

from __future__ import annotations

from typing import Any, Mapping

from lokay.envelope import ok


def select(
    picked: Mapping[str, Any],
    triage_run: Mapping[str, Any],
    *,
    enabled: bool,
) -> dict[str, Any]:
    triage = triage_run.get("triage")
    verdict = triage if isinstance(triage, Mapping) else {}
    if not verdict.get("repairable"):
        return ok(route="skip", reason="triage_did_not_request_repair")
    if not enabled:
        return ok(route="skip", reason="pr_repair_disabled", repairable=True)
    return ok(
        route="repair",
        reason=str(verdict.get("reason") or "pr_triage_requested_repair"),
        repo=str(picked.get("repo") or ""),
        pr=int(picked.get("pr") or 0),
        branch=str(picked.get("branch") or ""),
        review=dict(verdict.get("review") or {}),
    )
