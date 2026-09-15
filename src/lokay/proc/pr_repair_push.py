"""Write-ahead and exact-identity reconciliation for repair pushes."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping

from lokay.proc import pr_repair_receipts

_SHA = re.compile(r"^[a-f0-9]{40}$")


def _git_value(command_runner: Any, worktree: Path, *args: str) -> tuple[int, str, str]:
    from lokay.runner import git_spec

    result = command_runner.run(
        git_spec(list(args), cwd=worktree, timeout_seconds=60), live=True
    )
    return result.returncode, str(result.stdout or "").strip(), str(result.stderr or "").strip()


def prepare_live_push(
    *,
    config_path: str | None,
    repo: str,
    pr: int,
    branch: str,
    worktree: str | Path,
    start_head_sha: str,
    repair_kind: str,
    reviewed_head_sha: str = "",
    task: Mapping[str, Any] | None = None,
    findings: list[dict[str, Any]] | None = None,
    task_identity_sha256: str = "",
    review_result_sha256: str = "",
) -> dict[str, Any]:
    """Persist+fsync exact target and mark attempt before the caller can push."""
    from lokay.config import load_config
    from lokay.proc._common import mutations_allowed, runner as make_runner

    start = str(start_head_sha or "").lower()
    if not _SHA.fullmatch(start) or pr <= 0 or not repo or not branch:
        return {"ok": False, "route": "fail_closed", "reason": "repair_push_identity_missing"}
    cfg = None
    try:
        cfg = load_config(config_path)
        mutations_allowed(live_flag=True, cfg=cfg)
        command_runner = make_runner(cfg)
        path = Path(worktree)
        head_status, target, head_error = _git_value(
            command_runner, path, "rev-parse", "--verify", "HEAD^{commit}"
        )
        branch_status, local_branch, branch_error = _git_value(
            command_runner, path, "symbolic-ref", "--quiet", "--short", "HEAD"
        )
        clean_status, dirty, clean_error = _git_value(
            command_runner, path, "status", "--porcelain=v1", "--untracked-files=all"
        )
    except Exception as exc:
        return {
            "ok": False, "route": "fail_closed",
            "reason": "repair_push_preflight_failed",
            "detail": f"{type(exc).__name__}: {exc}",
        }
    if head_status != 0 or head_error or not _SHA.fullmatch(target.lower()):
        return {"ok": False, "route": "fail_closed", "reason": "repair_push_target_sha_unavailable"}
    target = target.lower()
    if branch_status != 0 or branch_error or local_branch != branch:
        return {"ok": False, "route": "fail_closed", "reason": "repair_push_local_branch_mismatch"}
    if clean_status != 0 or clean_error or dirty:
        return {"ok": False, "route": "fail_closed", "reason": "repair_push_worktree_dirty"}
    if target == start:
        return {"ok": False, "route": "fail_closed", "reason": "repair_push_no_new_sha"}
    try:
        intent = pr_repair_receipts.build_push_intent(
            repo=repo, pr=pr, branch=branch, repair_kind=repair_kind,
            start_head_sha=start, target_head_sha=target,
            reviewed_head_sha=reviewed_head_sha, task=task, findings=findings,
            task_identity_sha256=task_identity_sha256,
            review_result_sha256=review_result_sha256,
        )
        prepared = pr_repair_receipts.prepare_push_intent(
            repo=repo, pr=pr, intent=intent,
            budget=max(1, int(cfg.max_request_changes_per_pr)),
            state_dir=cfg.state_path.expanduser().resolve().parent,
        )
        if prepared.get("route") != "recorded":
            return {"ok": False, **prepared}
        attempted = pr_repair_receipts.mark_push_attempted(
            repo=repo, pr=pr, intent_sha256=intent["intent_sha256"],
            state_dir=cfg.state_path.expanduser().resolve().parent,
        )
    except Exception:
        return {"ok": False, "route": "fail_closed", "reason": "repair_push_intent_persist_failed"}
    if attempted.get("route") != "ready":
        return {"ok": False, **attempted}
    return {
        "ok": True, "route": "ready", "head_sha": target,
        "intent_sha256": intent["intent_sha256"],
    }


def reconcile_pending_push(
    *,
    repo: str,
    pr: int,
    config_path: str | None,
    live: bool,
    budget: int | None = None,
    home: Path | str | None = None,
    state_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Confirm a push only from a live OPEN PR view matching its full identity."""
    try:
        receipt = pr_repair_receipts.read(repo, pr, home=home, state_dir=state_dir)
    except (OSError, ValueError, TypeError):
        return {"ok": True, "route": "fail_closed", "reason": "pr_repair_receipt_invalid"}
    pending = receipt.get("pending_push")
    if pending is None:
        return {
            "ok": True, "route": "none",
            "attempts": int(receipt.get("attempts") or 0),
            "budget": int(receipt.get("budget") or budget or 1),
        }
    if not live:
        return {
            "ok": True, "route": "fail_closed",
            "reason": "repair_push_reconciliation_requires_live",
            "attempts": int(receipt.get("attempts") or 0),
            "budget": int(receipt.get("budget") or budget or 1),
        }
    if not pending.get("push_attempted"):
        return {
            "ok": True, "route": "fail_closed",
            "reason": "repair_push_attempt_not_recorded",
            "attempts": int(receipt.get("attempts") or 0),
            "budget": int(receipt.get("budget") or budget or 1),
        }
    from lokay.proc.probe_pr_state import probe

    try:
        identity = probe(repo=repo, pr=pr, live=True, config_path=config_path)
    except Exception:
        identity = {}
    if identity.get("ok") is not True or identity.get("route") == "unavailable" or identity.get("probe_failed"):
        return {
            "ok": True, "route": "fail_closed",
            "reason": "repair_push_remote_identity_unavailable",
            "attempts": int(receipt.get("attempts") or 0),
            "budget": int(receipt.get("budget") or budget or 1),
        }
    intent = dict(pending)
    if (
        identity.get("route") != "open"
        or str(identity.get("state") or "").upper() != "OPEN"
        or str(identity.get("head_ref") or "") != intent["branch"]
        or str(identity.get("head_ref_sha") or "").lower() != intent["target_head_sha"]
        or str(identity.get("head_repo") or "").lower() != repo.lower()
    ):
        return {
            "ok": True, "route": "fail_closed",
            "reason": "repair_push_remote_identity_mismatch",
            "attempts": int(receipt.get("attempts") or 0),
            "budget": int(receipt.get("budget") or budget or 1),
        }
    confirmed = pr_repair_receipts.confirm_pending_push(
        repo=repo, pr=pr, intent_sha256=intent["intent_sha256"],
        remote_head_sha=str(identity["head_ref_sha"]),
        remote_branch=str(identity["head_ref"]),
        remote_repo=str(identity["head_repo"]),
        remote_state=str(identity["state"]),
        budget=max(1, int(budget or receipt.get("budget") or 1)),
        home=home, state_dir=state_dir,
    )
    if confirmed.get("route") != "confirmed":
        return {
            "ok": True, "route": "fail_closed",
            "reason": str(confirmed.get("reason") or "repair_push_confirmation_failed"),
            "attempts": int(receipt.get("attempts") or 0),
            "budget": int(receipt.get("budget") or budget or 1),
        }
    return {"ok": True, "route": "confirmed", **confirmed}
