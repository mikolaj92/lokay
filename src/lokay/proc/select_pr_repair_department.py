"""Authorize the factory-level PR-repair department after the PR sieve."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from lokay.envelope import ok
from lokay.proc import pr_repair_push, pr_repair_receipts


def _task_identity(task: Mapping[str, Any]) -> str:
    canonical = json.dumps(task, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def select(
    triage_run: Mapping[str, Any],
    *,
    enabled: bool,
    triage_ran: bool,
    config_path: str | None = None,
    live: bool = False,
    home: Path | str | None = None,
    state_dir: Path | str | None = None,
    budget: int | None = None,
) -> dict[str, Any]:
    payload = dict(triage_run or {})
    nested = payload.get("result")
    if isinstance(nested, Mapping):
        payload = {**payload, **dict(nested)}
    triage = payload.get("triage")
    verdict = triage if isinstance(triage, Mapping) else {}
    if str(payload.get("verdict") or "") == "repair":
        verdict = {**verdict, "repairable": True}
    repo = str(payload.get("repo") or "")
    try:
        pr = int(payload.get("pr") or 0)
    except (TypeError, ValueError):
        pr = 0
    branch = str(payload.get("branch") or "")
    budget_n = (
        max(1, int(budget)) if budget is not None
        else pr_repair_receipts.resolve_budget(config_path)
    )
    resolved_state = (
        Path(state_dir) if state_dir is not None
        else pr_repair_receipts.resolve_state_dir(config_path)
    )
    try:
        receipt = (
            pr_repair_receipts.read(repo, pr, home=home, state_dir=resolved_state)
            if repo and pr > 0 else {}
        )
    except (OSError, ValueError, TypeError):
        return ok(
            route="fail_closed", reason="pr_repair_receipt_invalid",
            repairable=bool(verdict.get("repairable")),
            repo=repo, pr=pr, branch=branch,
        )
    if receipt.get("pending_push") is not None:
        recovery = pr_repair_push.reconcile_pending_push(
            repo=repo, pr=pr, config_path=config_path, live=live,
            budget=budget_n, home=home, state_dir=resolved_state,
        )
        if recovery.get("route") != "confirmed":
            return ok(
                route="fail_closed",
                reason=str(recovery.get("reason") or "repair_push_confirmation_failed"),
                attempts=int(recovery.get("attempts") or receipt.get("attempts") or 0),
                budget=int(recovery.get("budget") or receipt.get("budget") or budget_n),
                repo=repo, pr=pr, branch=branch,
            )
        return ok(
            route="skip", reason="repair_push_recovered",
            attempts=int(recovery.get("attempts") or 0),
            budget=int(recovery.get("budget") or budget_n),
            parked=bool(recovery.get("parked")),
            last_head_sha=str(recovery.get("head_sha") or ""),
            last_reviewed_sha=str(recovery.get("reviewed_sha") or ""),
            repair_kind=str(recovery.get("repair_kind") or ""),
            repo=repo, pr=pr, branch=str(receipt["pending_push"].get("branch") or branch),
        )
    if not enabled:
        return ok(route="skip", reason="pr_repair_disabled")
    if not repo or pr <= 0:
        return ok(route="skip", reason="no_triage_verdict")
    if not verdict.get("repairable"):
        return ok(route="skip", reason="no_triage_verdict")
    raw_review = verdict.get("review") or payload.get("review") or {}
    review = dict(raw_review) if isinstance(raw_review, Mapping) else {}
    # Explicit repair fields (including empty CI fields) outrank review evidence.
    handoff = {**review, **verdict, **payload}
    task = dict(handoff.get("task") or {})
    findings = list(handoff.get("findings") or [])
    repair_kind = str(verdict.get("repair_kind") or "")
    reviewed_head_sha = str(handoff.get("reviewed_head_sha") or "")
    repair_push_intent_sha256 = str(
        payload.get("repair_push_intent_sha256") or verdict.get("repair_push_intent_sha256") or ""
    )
    repair_start_head_sha = str(
        payload.get("repair_start_head_sha") or payload.get("head_sha")
        or verdict.get("repair_start_head_sha") or verdict.get("head_sha") or ""
    ).lower()
    task_digest = str(handoff.get("task_identity_sha256") or "")
    review_result_digest = str(handoff.get("review_result_sha256") or "")
    if repair_kind not in {"ci", "review"}:
        return ok(
            route="fail_closed", reason="repair_kind_invalid",
            repairable=False, repo=repo, pr=pr, branch=branch, needs_review=True,
        )
    if repair_kind == "ci" and (
        not re.fullmatch(r"[a-f0-9]{40}", repair_start_head_sha)
        or task or findings or reviewed_head_sha or task_digest or review_result_digest
    ):
        return ok(
            route="fail_closed", reason=(
                "ci_repair_start_head_missing" if not re.fullmatch(r"[a-f0-9]{40}", repair_start_head_sha)
                else "ci_repair_contains_review_handoff"
            ),
            repairable=False, repo=repo, pr=pr, branch=branch, needs_review=True,
        )
    if repair_kind == "review" and (
        review.get("verdict") != "request_changes" or not task or not findings
        or not reviewed_head_sha or not re.fullmatch(r"[a-f0-9]{40}", reviewed_head_sha)
        or not task_digest or not re.fullmatch(r"[a-f0-9]{64}", task_digest)
        or not review_result_digest or not re.fullmatch(r"[a-f0-9]{64}", review_result_digest)
        or task.get("state") != "OPEN" or task.get("repo") != repo
        or task.get("type") != "Issue"
        or _task_identity(task) != task_digest
        or reviewed_head_sha != str(review.get("reviewed_head_sha") or "").lower()
        or not re.fullmatch(r"[a-f0-9]{40}", repair_start_head_sha)
        or repair_start_head_sha != reviewed_head_sha
        or task_digest != str(review.get("task_identity_sha256") or "").lower()
        or review_result_digest != str(review.get("review_result_sha256") or "").lower()
    ):
        return ok(
            route="fail_closed", reason="review_repair_handoff_incomplete",
            repairable=False, repo=repo, pr=pr, branch=branch, needs_review=True,
        )
    attempts = int(receipt.get("attempts") or 0)
    receipt_budget = max(1, int(receipt.get("budget") or budget_n))
    parked = bool(receipt.get("parked")) or attempts >= receipt_budget
    if parked:
        return ok(
            route="fail_closed", reason="pr_repair_budget_exhausted",
            repairable=True, parked=True, attempts=attempts, budget=receipt_budget,
            repo=repo, pr=pr, branch=branch, task=task, findings=findings,
            reviewed_head_sha=reviewed_head_sha, task_identity_sha256=task_digest,
            review_result_sha256=review_result_digest, repair_kind=repair_kind,
            repair_start_head_sha=repair_start_head_sha,
        )
    return ok(
        route="repair", reason=str(verdict.get("reason") or "pr_triage_requested_repair"),
        repo=repo, pr=pr, branch=branch, review=review, task=task, findings=findings,
        reviewed_head_sha=reviewed_head_sha, task_identity_sha256=task_digest,
        review_result_sha256=review_result_digest, repair_kind=repair_kind,
        repair_push_intent_sha256=repair_push_intent_sha256,
        repair_start_head_sha=repair_start_head_sha, attempts=attempts,
        budget=receipt_budget, parked=False,
    )
