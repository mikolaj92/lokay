"""Authorize the factory-level PR-repair department after the PR sieve."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from lokay.envelope import ok
from lokay.proc import pr_repair_receipts


def select(
    triage_run: Mapping[str, Any],
    *,
    enabled: bool,
    triage_ran: bool,
    config_path: str | None = None,
    home: Path | str | None = None,
    state_dir: Path | str | None = None,
    budget: int | None = None,
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
    repo = str(payload.get("repo") or "")
    pr = int(payload.get("pr") or 0)
    branch = str(payload.get("branch") or "")
    review = dict(verdict.get("review") or payload.get("review") or {})
    budget_n = (
        max(1, int(budget))
        if budget is not None
        else pr_repair_receipts.resolve_budget(config_path)
    )
    resolved_state = (
        Path(state_dir)
        if state_dir is not None
        else pr_repair_receipts.resolve_state_dir(config_path)
    )
    receipt = pr_repair_receipts.read(
        repo, pr, home=home, state_dir=resolved_state
    )
    attempts = int(receipt.get("attempts") or 0)
    receipt_budget = max(1, int(receipt.get("budget") or budget_n))
    parked = bool(receipt.get("parked")) or attempts >= receipt_budget
    if parked:
        return ok(
            route="fail_closed",
            reason="pr_repair_budget_exhausted",
            repairable=True,
            parked=True,
            attempts=attempts,
            budget=receipt_budget,
            repo=repo,
            pr=pr,
            branch=branch,
            review=review,
        )
    return ok(
        route="repair",
        reason=str(verdict.get("reason") or "pr_triage_requested_repair"),
        repo=repo,
        pr=pr,
        branch=branch,
        review=review,
        attempts=attempts,
        budget=receipt_budget,
        parked=False,
    )
