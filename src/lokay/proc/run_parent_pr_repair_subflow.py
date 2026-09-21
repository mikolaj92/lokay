"""Parent NODE slot: invoke `pr_repair` after an authored sieve verdict."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

from lokay.compose.pr_repair import compose_pr_repair
from lokay.proc import pr_repair_push, pr_repair_receipts


def _repair_meta(
    result: Mapping[str, Any] | None, expected: Mapping[str, Any] | None = None
) -> tuple[str, str, str, str, int, bool, str]:
    outer = dict(result or {})
    payload = dict(outer)
    nested = payload.get("result")
    if isinstance(nested, Mapping):
        payload = {**payload, **dict(nested)}
    head = str(payload.get("head_sha") or "")
    terminal = str(
        payload.get("terminal") or payload.get("route") or payload.get("error") or ""
    )
    repo = str(payload.get("repo") or "")
    pr = int(payload.get("pr") or 0)
    reviewed = str(payload.get("reviewed_head_sha") or "")
    task = payload.get("task")
    findings = payload.get("findings")
    task_digest = str(payload.get("task_identity_sha256") or "")
    result_digest = str(payload.get("review_result_sha256") or "")
    expected_handoff = dict(expected or {})
    repair_kind = str(expected_handoff.get("kind") or "")
    expected_task = expected_handoff.get("task")
    expected_findings = expected_handoff.get("findings")
    start_head_sha = str(expected_handoff.get("start_head_sha") or "")
    expected_task_digest = str(expected_handoff.get("task_identity_sha256") or "")
    expected_result_digest = str(expected_handoff.get("review_result_sha256") or "")
    if repair_kind == "ci":
        confirmed = (
            outer.get("ok") is True
            and payload.get("repaired") is True
            and payload.get("published") is True
            and terminal == "publish"
            and bool(re.fullmatch(r"[a-f0-9]{40}", head))
            and bool(re.fullmatch(r"[a-f0-9]{40}", start_head_sha))
            and head != start_head_sha
            and bool(repo)
            and pr > 0
            and task in ({}, None) and findings in ([], None)
            and not reviewed and not task_digest and not result_digest
        )
        return head, terminal, "", repo, pr, confirmed, ""
    if repair_kind != "review":
        return head, terminal, reviewed, repo, pr, False, task_digest
    if not isinstance(task, Mapping) or not task or not isinstance(findings, list) or not findings:
        return head, terminal, reviewed, repo, pr, False, ""
    if (
        not isinstance(expected_task, Mapping) or not expected_task
        or not isinstance(expected_findings, list) or not expected_findings
        or not re.fullmatch(r"[a-f0-9]{64}", expected_task_digest)
        or not re.fullmatch(r"[a-f0-9]{64}", expected_result_digest)
    ):
        return head, terminal, reviewed, repo, pr, False, task_digest
    confirmed = (
        outer.get("ok") is True
        and payload.get("repaired") is True
        and payload.get("published") is True
        and terminal == "publish"
        and bool(re.fullmatch(r"[a-f0-9]{40}", head))
        and bool(re.fullmatch(r"[a-f0-9]{40}", reviewed))
        and head != reviewed
        and bool(repo)
        and pr > 0
        and task == expected_task
        and findings == expected_findings
        and task_digest == expected_task_digest
        and result_digest == expected_result_digest
    )
    return head, terminal, reviewed, repo, pr, confirmed, task_digest


def _remote_head(repo: str, pr: int, *, config_path: str | None, live: bool) -> str:
    if not live:
        return "planned"
    import re
    from lokay.config import load_config
    from lokay.gh_prs import gh_json
    from lokay.proc._common import runner as make_runner

    cfg = load_config(config_path)
    view = gh_json(
        make_runner(cfg),
        ["pr", "view", str(pr), "--repo", repo, "--json", "headRefOid"],
        live=True,
    )
    head = str(view.get("headRefOid") or "").lower()
    return head if re.fullmatch(r"[a-f0-9]{40}", head) else ""


def _review_task_is_current(
    selected: Mapping[str, Any], *, config_path: str | None, live: bool
) -> bool:
    """Require the original OPEN issue to still match before review repair."""
    if not live or str(selected.get("repair_kind") or "") != "review":
        return True
    task = selected.get("task")
    review = selected.get("review")
    if not isinstance(task, Mapping) or not task or not isinstance(review, Mapping):
        return False
    expected_digest = str(selected.get("task_identity_sha256") or "").lower()
    if not re.fullmatch(r"[a-f0-9]{64}", expected_digest):
        return False
    canonical_bytes = json.dumps(
        dict(task), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    if hashlib.sha256(canonical_bytes).hexdigest() != expected_digest:
        return False
    if (
        dict(review.get("task") or {}) != dict(task)
        or str(review.get("task_identity_sha256") or "").lower() != expected_digest
    ):
        return False
    try:
        from lokay.config import load_config
        from lokay.proc._common import runner as make_runner
        from lokay.pr_review_io import resolve_canonical_task

        cfg = load_config(config_path)
        canonical = resolve_canonical_task(
            make_runner(cfg),
            str(selected.get("repo") or ""),
            pr=int(selected.get("pr") or 0),
            branch=str(selected.get("branch") or ""),
            branch_prefix=cfg.branch_prefix,
            live=True,
        )
    except Exception:
        return False
    canonical_task = {
        key: value for key, value in canonical.items() if key != "identity_sha256"
    }
    return (
        canonical_task == dict(task)
        and str(canonical.get("identity_sha256") or "").lower() == expected_digest
    )


def run(selected: dict[str, Any], *, config_path: str | None, live: bool) -> dict[str, Any]:
    budget = pr_repair_receipts.resolve_budget(config_path)
    state_dir = pr_repair_receipts.resolve_state_dir(config_path)
    result: dict[str, Any]
    if (
        str(selected.get("repair_kind") or "") == "review"
        and not _review_task_is_current(
            selected, config_path=config_path, live=live
        )
    ):
        receipt = pr_repair_receipts.read(
            str(selected.get("repo") or ""),
            int(selected.get("pr") or 0),
            state_dir=state_dir,
        )
        return {
            "ok": True,
            "route": "fail_closed",
            "reason": "review_repair_task_identity_drift",
            "attempts": int(receipt.get("attempts") or 0),
            "budget": int(receipt.get("budget") or budget),
            "parked": bool(receipt.get("parked")),
        }
    # An explicit empty digest is CI authority, not missing review evidence.
    review = dict(selected.get("review") or {})
    review_result_sha256 = str(
        selected.get("review_result_sha256", review.get("review_result_sha256")) or ""
    )
    try:
        result = compose_pr_repair(
            config_path=config_path,
            repo=str(selected["repo"]),
            pr_number=int(selected["pr"]),
            branch=str(selected["branch"]),
            review=dict(selected.get("review") or {}),
            task=dict(selected.get("task") or {}),
            findings=list(selected.get("findings") or []),
            reviewed_head_sha=str(selected.get("reviewed_head_sha") or ""),
            task_identity_sha256=str(selected.get("task_identity_sha256") or ""),
            review_result_sha256=review_result_sha256,
            repair_kind=str(selected.get("repair_kind") or ""),
            repair_start_head_sha=str(selected.get("repair_start_head_sha") or ""),
            live=live,
        )
    except Exception as exc:  # noqa: BLE001 — fail closed without consuming an attempt
        result = {"ok": False, "error": "compose_error", "terminal": "compose_error"}
    nested = result.get("result") if isinstance(result.get("result"), Mapping) else {}
    skipped = bool(result.get("skipped") or (nested or {}).get("skipped"))
    if skipped:
        receipt = pr_repair_receipts.read(
            str(selected["repo"]),
            int(selected["pr"]),
            state_dir=state_dir,
        )
        return {
            "ok": True,
            "route": "skip",
            "reason": str(
                result.get("reason")
                or (nested or {}).get("reason")
                or "pr_already_merged"
            ),
            "repair": result,
            "attempts": int(receipt.get("attempts") or 0),
            "budget": int(receipt.get("budget") or budget),
            "parked": bool(receipt.get("parked")),
        }
    expected_handoff = {
        "kind": str(selected.get("repair_kind") or ""),
        "start_head_sha": str(selected.get("repair_start_head_sha") or selected.get("head_sha") or ""),
        "task": dict(selected.get("task") or {}),
        "findings": list(selected.get("findings") or []),
        "reviewed_head_sha": str(selected.get("reviewed_head_sha") or ""),
        "task_identity_sha256": str(selected.get("task_identity_sha256") or ""),
        "review_result_sha256": review_result_sha256,
    }
    head_sha, terminal, reviewed_sha, result_repo, result_pr, confirmed, _task_digest = _repair_meta(
        result, expected_handoff
    )
    repo, pr = str(selected["repo"]), int(selected["pr"])
    branch = str(selected.get("branch") or "")
    nested_result = result.get("result")
    if not isinstance(nested_result, Mapping):
        nested_result = {}
    result_branch = str(nested_result.get("branch") or result.get("branch") or "")
    failure_reason = str(nested_result.get("reason") or result.get("reason") or "repair_push_not_confirmed")
    confirmed = (
        confirmed and result_repo == repo and result_pr == pr
        and result_branch == branch
    )
    if not live:
        try:
            receipt = pr_repair_receipts.read(repo, pr, state_dir=state_dir)
        except (OSError, ValueError, TypeError):
            receipt = {}
        return {
            "ok": True,
            "route": "planned" if confirmed else "fail_closed",
            "reason": "repair_push_not_live" if confirmed else failure_reason,
            "repair": result,
            "attempts": int(receipt.get("attempts") or 0),
            "budget": int(receipt.get("budget") or budget),
            "parked": bool(receipt.get("parked")),
        }
    try:
        receipt = pr_repair_receipts.read(repo, pr, state_dir=state_dir)
    except (OSError, ValueError, TypeError):
        return {
            "ok": True, "route": "fail_closed",
            "reason": "pr_repair_receipt_invalid",
            "repair": result, "attempts": 0, "budget": budget,
            "parked": False,
        }
    pending = receipt.get("pending_push")
    intent_digest = str(nested_result.get("repair_push_intent_sha256")
                        or result.get("repair_push_intent_sha256") or "")
    intent_matches_result = False
    if isinstance(pending, Mapping):
        try:
            intent = pr_repair_receipts._validate_intent(pending, repo=repo, pr=pr)
        except ValueError:
            intent = {}
        intent_matches_result = bool(
            intent
            and intent.get("push_attempted") is True
            and intent.get("branch") == branch
            and intent.get("repair_kind") == expected_handoff["kind"]
            and intent.get("start_head_sha") == expected_handoff["start_head_sha"]
            and intent.get("target_head_sha") == head_sha.lower()
            and intent.get("intent_sha256") == intent_digest
        )
        if expected_handoff["kind"] == "review":
            expected_findings_sha = hashlib.sha256(json.dumps(
                expected_handoff["findings"], ensure_ascii=False, sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")).hexdigest()
            intent_matches_result = bool(
                intent_matches_result
                and intent.get("reviewed_head_sha") == reviewed_sha.lower()
                and intent.get("task_identity_sha256") == expected_handoff["task_identity_sha256"]
                and intent.get("review_result_sha256") == expected_handoff["review_result_sha256"]
                and intent.get("findings_sha256") == expected_findings_sha
            )
    if not confirmed or not intent_matches_result:
        return {
            "ok": True, "route": "fail_closed",
            "reason": "repair_push_intent_result_mismatch" if confirmed else failure_reason,
            "repair": result,
            "attempts": int(receipt.get("attempts") or 0),
            "budget": int(receipt.get("budget") or budget),
            "parked": False,
        }
    reconciliation = pr_repair_push.reconcile_pending_push(
        repo=repo, pr=pr, config_path=config_path, live=True,
        budget=budget, state_dir=state_dir,
    )
    if reconciliation.get("route") != "confirmed":
        return {
            "ok": True, "route": "fail_closed",
            "reason": str(reconciliation.get("reason") or "repair_push_not_confirmed"),
            "repair": result,
            "attempts": int(reconciliation.get("attempts") or receipt.get("attempts") or 0),
            "budget": int(reconciliation.get("budget") or budget),
            "parked": False,
        }
    return {
        "ok": True, "route": "completed",
        "repair": result,
        "repair_push_intent_sha256": intent_digest,
        "attempts": int(reconciliation.get("attempts") or 0),
        "budget": int(reconciliation.get("budget") or budget),
        "parked": bool(reconciliation.get("parked")),
    }
