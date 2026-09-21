"""Fala organ routing — one job family per module."""

from __future__ import annotations

import subprocess
from typing import Any

from lokay.organ.common import (
    _require_test_local,
)


def _clean_head(worktree: str) -> str:
    """Read a clean local commit; do not turn mutable worktree contents into evidence."""
    from lokay.code.pr import require_head_sha

    def git(*args: str) -> str:
        return subprocess.check_output(
            ["git", "-C", worktree, *args], text=True, stderr=subprocess.PIPE,
            timeout=30,
        ).strip()

    head = require_head_sha(git("rev-parse", "HEAD"))
    if git("status", "--porcelain", "--untracked-files=all"):
        raise ValueError("local test worktree is dirty")
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

    if atom == "pr_merge":
        assert repo and pr_number is not None
        from lokay.config import load_config
        from lokay.merge_policy import decide_auto_merge

        merge_cfg = load_config(
            str(inputs.get("config_path") or inputs.get("config") or "") or None
        )
        checks = up.get("pr_checks") or {}
        review = up.get("publish_pr_review") or up.get("pr_review") or {}
        # Trusted auto-merge gate (fail closed). Pending → waiting; red → repair;
        # secrets / fail_closed / escalated needs-review never merge.
        gate = decide_auto_merge(
            merge_enabled=bool(merge_cfg.merge_enabled),
            require_checks=bool(merge_cfg.require_checks),
            require_llm_review=bool(merge_cfg.require_llm_review),
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
        from lokay.proc.publish_delivery_receipt import publish
        from lokay.config import load_config
        from lokay.proc._common import runner as make_runner

        closed = up.get("close_issue") or {}
        if issue_number is None and closed.get("repo") == repo:
            issue_number = closed.get("issue")
        if not repo or type(pr_number) is not int or type(issue_number) is not int or issue_number < 1:
            return {"ok": True, "route": "pending", "confirmed": False, "reason": "receipt_identity_missing"}
        receipt_cfg = load_config(str(inputs.get("config_path") or inputs.get("config") or "") or None)
        carrier = make_runner(receipt_cfg)

        def read_pr(observed_repo: str, observed_pr: int) -> dict[str, Any]:
            from lokay.gh_prs import gh_json

            return gh_json(
                carrier,
                [
                    "pr",
                    "view",
                    str(observed_pr),
                    "--repo",
                    observed_repo,
                    "--json",
                    "body,headRefOid,mergeCommit,mergedAt",
                ],
                live=bool(inputs.get("live")),
            )

        def read_issue(observed_repo: str, observed_issue: int) -> dict[str, Any]:
            from lokay.gh_prs import gh_json

            return gh_json(
                carrier,
                [
                    "issue",
                    "view",
                    str(observed_issue),
                    "--repo",
                    observed_repo,
                    "--json",
                    "state",
                ],
                live=bool(inputs.get("live")),
            )

        def main_contains(observed_repo: str, head: str) -> bool:
            from lokay.gh_prs import gh_text

            return bool(
                gh_text(
                    carrier,
                    [
                        "api",
                        f"repos/{observed_repo}/compare/{head}...main",
                        "--jq",
                        ".status",
                    ],
                    live=bool(inputs.get("live")),
                    require_success=True,
                ).strip()
                in {"ahead", "identical"}
            )

        def edit_pr(observed_repo: str, observed_pr: int, body: str) -> str:
            from lokay.gh_prs import gh_text

            return gh_text(
                carrier,
                [
                    "pr",
                    "edit",
                    str(observed_pr),
                    "--repo",
                    observed_repo,
                    "--body",
                    body,
                ],
                live=bool(inputs.get("live")),
                require_success=True,
            )

        return publish(
            repo=repo,
            pr=pr_number,
            issue=issue_number,
            merge=up.get("pr_merge") or {},
            close=up.get("close_issue") or {},
            live=bool(inputs.get("live")),
            read_pr=read_pr,
            read_issue=read_issue,
            main_contains=main_contains,
            edit_pr=edit_pr,
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
