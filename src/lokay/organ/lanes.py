"""Fala organ routing — one job family per module."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from lokay.organ.common import (
    _require_test_local,
)


def _clean_head(worktree: str) -> str:
    """Read a clean local commit; do not turn mutable worktree contents into evidence."""
    from lokay.code.pr import require_head_sha
    from lokay.repair_worktree_dirt import repair_worktree_dirt
    from lokay.runner import Runner

    def git(*args: str) -> str:
        return subprocess.check_output(
            ["git", "-C", worktree, *args], text=True, stderr=subprocess.PIPE,
            timeout=30,
        ).strip()

    head = require_head_sha(git("rev-parse", "HEAD"))
    if repair_worktree_dirt(Runner(), Path(worktree)) not in {"clean", "evidence"}:
        raise ValueError("local test worktree has product dirt or unavailable status")
    return head


def run_merge_tests(run, *, review: dict, **kwargs) -> dict:
    """Attest the existing test child at its execution boundary (including cache/skip)."""
    from lokay.code.pr import require_head_sha

    try:
        head = require_head_sha((review.get("decision") or {}).get("reviewed_head_sha"))
        if _clean_head(kwargs["worktree"]) != head:
            raise ValueError("local test head differs from reviewed head")
        result = run(**kwargs)
        if _clean_head(kwargs["worktree"]) != head:
            raise ValueError("local test head changed during verification")
    except (ValueError, LookupError, OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "skipped": True, "waiting": True,
                "reason": "merge_test_identity_unverified", "error": str(exc)}
    if result.get("ok") is True and result.get("passed") is not False:
        result = {**result, "tested_head_sha": head}
    return result


def handle_lanes(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    from lokay.proc import (
        close_issue,
        get_issue,
        pr_checks,
        pr_merge,
    )
    from lokay.stuck import issue_number_from_branch

    cfg = ctx["cfg"]
    live = ctx["live"]
    repo = ctx["repo"]
    issue_number = ctx["issue_number"]
    pr_number = ctx["pr_number"]
    branch = ctx["branch"]

    from lokay.atom_runtime import run_atom_main

    _run_atom_main = ctx.get("run_atom_main") or run_atom_main
    if atom == "get_issue":
        assert repo and issue_number is not None
        return _run_atom_main(
            get_issue.main,
            [*cfg, "--repo", repo, "--issue", str(issue_number)],
        )

    if atom == "pr_checks":
        assert repo and pr_number is not None
        return _run_atom_main(
            pr_checks.main,
            [*cfg, "--repo", repo, "--pr", str(pr_number)],
        )

    if atom == "prepare_delivery_closeout":
        from lokay.config import load_config
        from lokay.proc.delivery_closeout import prepare

        if issue_number is None:
            issue_number = issue_number_from_branch(branch, branch_prefix=str(inputs.get("branch_prefix") or "ai/fix"))
        return prepare(
            state_path=load_config(str(inputs.get("config_path") or "") or None).state_path,
            repo=repo, pr=pr_number, issue=issue_number or 0, branch=branch,
            review=up.get("publish_pr_review") or {}, tests=up.get("test_local") or {},
            live=bool(inputs.get("live")), keep_issue_open=bool(inputs.get('keep_issue_open')),
        )

    if atom == "pr_merge":
        assert repo and pr_number is not None
        from lokay.config import load_config
        from lokay.merge_policy import decide_merge

        merge_cfg = load_config(
            str(inputs.get("config_path") or inputs.get("config") or "") or None
        )
        checks = up.get("pr_checks") or {}
        review = up.get("publish_pr_review") or up.get("pr_review") or {}
        # The mode picks: off never merges, classify only on low risk, always
        # on any approval. Secrets, escalation, and red checks still block.
        gate = decide_merge(
            mode=merge_cfg.merge_mode,
            require_checks=bool(merge_cfg.require_checks),
            checks=checks,
            review=review,
            pr_labels=inputs.get("pr_labels") or inputs.get("labels"),
        )
        if gate.action != "merge":
            return {
                "ok": True,
                "skipped": True,
                "reason": gate.reason,
                "status": checks.get("status"),
                "repo": repo,
                "pr": pr_number,
                "review": review.get("decision") if isinstance(review, dict) else None,
                "repairable": gate.repairable,
                "waiting": gate.waiting,
                "needs_review": gate.needs_review,
                "merge_policy": gate.to_dict(),
            }
        refused = _require_test_local(up)
        if refused is not None:
            return refused
        from lokay.code.pr import require_head_sha

        try:
            head = require_head_sha((review.get("decision") or {}).get("reviewed_head_sha"))
            tested = (up.get("test_local") or {}).get("tested_head_sha")
            if tested != head:
                raise ValueError("local tests are not bound to the reviewed head")
            if review.get("head_sha") not in (None, head):
                raise ValueError("published review head differs from reviewed head")
            if checks.get("head_sha") not in (None, head):
                raise ValueError("checks head differs from reviewed head")
        except (ValueError, LookupError) as exc:
            return {"ok": True, "skipped": True, "waiting": True,
                    "reason": "merge_head_unverified", "error": str(exc)}
        if inputs.get('live'):
            from lokay.proc.delivery_closeout import validate
            try:
                intent = validate((up.get('prepare_delivery_closeout') or {}).get('intent') or {})
                if (intent['repo'], intent['pr'], intent['branch'], intent['head_sha']) != (repo, pr_number, branch, head):
                    raise ValueError('intent identity mismatch')
            except (ValueError, KeyError, TypeError):
                return {'ok': True, 'skipped': True, 'waiting': True,
                        'reason': 'delivery_closeout_intent_missing'}
        argv = [*cfg, *live, "--repo", repo, "--pr", str(pr_number),
                "--expected-head-sha", head]
        if issue_number is not None:
            argv.extend(["--issue", str(issue_number)])
        result = _run_atom_main(pr_merge.main, argv)
        if not result.get("ok"):
            # No retry with a fresh tip: next pass re-enters SHA-bound review.
            return {"ok": True, "skipped": True, "waiting": True,
                    "reason": "merge_not_confirmed", "error": result.get("error"),
                    "reviewed_head_sha": head}
        return result

    if atom == "publish_delivery_receipt":
        from lokay.proc.publish_delivery_receipt import publish_from_config

        if not inputs.get("live"):
            return {"ok":True, "route":"planned", "confirmed":False, "planned":True}
        closed = up.get("close_issue") or {}
        if issue_number is None and closed.get("repo") == repo:
            issue_number = closed.get("issue")
        if not repo or type(pr_number) is not int or type(issue_number) is not int or issue_number < 1:
            return {"ok": True, "route": "pending", "confirmed": False, "reason": "receipt_identity_missing"}
        return publish_from_config(
            config_path=str(inputs.get("config_path") or inputs.get("config") or "") or None,
            repo=repo, pr=pr_number, issue=issue_number,
            merge=up.get("pr_merge") or {}, close=closed,
            live=bool(inputs.get("live")), review=up.get("publish_pr_review"),
            tests=up.get("test_local"), closeout_intent=inputs.get('closeout_intent'),
        )

    if atom == "close_issue":
        assert repo
        if inputs.get("keep_issue_open"):
            return {
                "ok": True,
                "skipped": True,
                "reason": "self_repair_validation_pending",
            }
        merged = up.get("pr_merge") or {}
        # Only close after merge ran (live merged=true) or dry-run planned merge.
        if merged.get("skipped"):
            return {
                "ok": True,
                "skipped": True,
                "reason": "pr_merge_skipped",
                "repo": repo,
                "pr": pr_number,
            }
        if not (merged.get("merged") or merged.get("planned")):
            return {
                "ok": True,
                "skipped": True,
                "reason": "pr_not_merged",
                "repo": repo,
                "pr": pr_number,
            }
        if issue_number is None and branch:
            prefix = str(inputs.get("branch_prefix") or "ai/fix")
            issue_number = issue_number_from_branch(branch, branch_prefix=prefix)
        if issue_number is None:
            return {
                "ok": True,
                "skipped": True,
                "reason": "issue_number_unknown",
                "branch": branch,
                "pr": pr_number,
            }
        comment = str(
            inputs.get("comment") or f"Closed by Lokay after merging PR #{pr_number}."
        )
        return _run_atom_main(
            close_issue.main,
            [
                *cfg,
                *live,
                "--repo",
                repo,
                "--issue",
                str(issue_number),
                "--comment",
                comment,
            ],
        )

    if atom == "stage_label":
        stage = str(inputs.get("stage") or "").strip().lower()
        if not stage:
            return {"ok": False, "error": "stage_label requires config/input stage"}
        if issue_number is None and branch:
            prefix = str(inputs.get("branch_prefix") or "ai/fix")
            issue_number = issue_number_from_branch(branch, branch_prefix=prefix)
        if issue_number is None:
            return {
                "ok": True,
                "skipped": True,
                "reason": "issue_number_unknown",
                "stage": stage,
                "branch": branch,
                "pr": pr_number,
            }
        if stage in {"clear", "merged"}:
            merged = up.get("pr_merge") or {}
            if merged.get("skipped") or not (
                merged.get("merged") or merged.get("planned")
            ):
                return {
                    "ok": True,
                    "skipped": True,
                    "reason": "pr_not_merged",
                    "stage": stage,
                    "repo": repo,
                    "pr": pr_number,
                }
        from lokay.proc.stage_label_subflow import run

        return run(
            config_path=str(inputs.get("config_path") or "") or None,
            live=bool(inputs.get("live")),
            repo=repo,
            issue=int(issue_number),
            stage=stage,
            receipt=bool(inputs.get("receipt")),
            comment=str(inputs.get("comment") or ""),
        )

    return None
