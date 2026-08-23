"""Fala organ routing — one job family per module."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from lokay.models import Issue
from lokay.organ.common import (
    _cfg_flags,
    _live_flags,
    _localize_paths,
    _require_push,
    _require_real_diff,
    _require_test_local,
    _run_atom_main,
    _test_local_ok,
)
from lokay.prompts import (
    issue_fix_prompt,
    local_test_repair_prompt,
    pr_body,
    repair_pr_prompt,
    self_repair_prompt,
)


def handle_lanes(atom: str, inputs: dict[str, Any], up: dict[str, dict[str, Any]], ctx: dict[str, Any]) -> dict[str, Any] | None:
    from lokay.proc import (
        assign_issue, close_issue, commit_all, closeout_prs, compute_health,
        cycle_end, cycle_start, dispatch_implement, dispatch_triage, factory_begin,
        factory_tick, get_issue, host_ff, list_prs, make_branch, plan_issue,
        localize, pi_budget, plan_pass, pr_checks, pr_create, pr_label, pr_merge,
        pr_review, push_branch, record_pass, recovery_begin, recovery_incident,
        recovery_mill, recovery_observe, recovery_record, recovery_run_self_repair,
        resolve_conflicts, run_agent, select_implement, queue_conflict, stage_label,
        survey_inbox, survey_prs, survey_ready, survey_repos, test_local,
        triage_issue, intake_issue, issue_split, worktree_add, assert_real_diff,
        self_repair_activate, self_repair_close, self_repair_prepare,
        self_repair_preflight, self_repair_push_main, self_repair_validate,
    )
    from lokay.git_commit import branch_ahead_of_upstream
    from lokay.stuck import issue_number_from_branch
    cfg = ctx["cfg"]
    live = ctx["live"]
    repo = ctx["repo"]
    issue_number = ctx["issue_number"]
    pr_number = ctx["pr_number"]
    repair_mode = ctx["repair_mode"]
    branch = ctx["branch"]

    import lokay.fala_organ as _fo
    _run_atom_main = _fo._run_atom_main
    branch_ahead_of_upstream = getattr(_fo, "branch_ahead_of_upstream", None)
    if branch_ahead_of_upstream is None:
        from lokay.git_commit import branch_ahead_of_upstream

    if atom == "get_issue":
        assert repo and issue_number is not None
        return _run_atom_main(
            get_issue.main,
            [*cfg, "--repo", repo, "--issue", str(issue_number)],
        )

    if atom == "triage_issue":
        assert repo and issue_number is not None
        return _run_atom_main(
            triage_issue.main,
            [*cfg, *live, "--repo", repo, "--issue", str(issue_number)],
        )

    if atom == "intake_issue":
        assert repo and issue_number is not None
        argv = [*cfg, *live, "--repo", repo, "--issue", str(issue_number)]
        triage = up.get("triage_issue") or {}
        triage_decision = triage.get("decision")
        if isinstance(triage_decision, dict) and triage_decision.get("decision") == "ready":
            argv.append("--candidate-ready")
        if isinstance(triage_decision, dict) and triage_decision.get("decision") == "split":
            argv.append("--candidate-split")
        if inputs.get("require_ready"):
            argv.append("--require-ready")
        return _run_atom_main(intake_issue.main, argv)

    if atom == "issue_split":
        assert repo and issue_number is not None
        argv = [*cfg, *live, "--repo", repo, "--issue", str(issue_number)]
        intake = up.get("intake_issue") or {}
        intake_decision = intake.get("decision")
        if isinstance(intake_decision, dict):
            argv.extend(["--intake-decision", json.dumps(intake_decision, separators=(",", ":"))])
            if intake_decision.get("reason"):
                argv.extend(["--reason", str(intake_decision.get("reason"))])
        elif intake_decision:
            argv.extend(["--intake-decision", str(intake_decision)])
        # Also honor triage split when intake skipped after already-decided tracker demotion.
        triage = up.get("triage_issue") or {}
        triage_decision = triage.get("decision")
        if (
            isinstance(triage_decision, dict)
            and triage_decision.get("decision") == "split"
            and not (isinstance(intake_decision, dict) and intake_decision.get("decision"))
        ):
            argv.extend(["--intake-decision", "split", "--reason", str(triage_decision.get("reason") or "too_large_split")])
        return _run_atom_main(issue_split.main, argv)

    if atom == "pr_checks":
        assert repo and pr_number is not None
        return _run_atom_main(
            pr_checks.main,
            [*cfg, "--repo", repo, "--pr", str(pr_number)],
        )

    if atom == "pr_review":
        assert repo and pr_number is not None
        # The graph always contains the review effector, but review policy is
        # optional.  Bypass the executor entirely when deterministic merge is
        # configured; downstream merge treats merge_ok=true as approval.
        from lokay.config import load_config

        review_cfg = load_config(str(inputs.get("config_path") or inputs.get("config") or "") or None)
        if not review_cfg.require_llm_review:
            return {
                "ok": True,
                "skipped": True,
                "reason": "llm_review_not_required",
                "decision": {"verdict": "approve"},
                "merge_ok": True,
                "repo": repo,
                "pr": pr_number,
            }
        checks = up.get("pr_checks") or {}
        argv = [
            *cfg,
            *live,
            "--repo",
            repo,
            "--pr",
            str(pr_number),
        ]
        if branch:
            argv.extend(["--branch", branch])
        checks_text = str(checks.get("text") or inputs.get("checks_text") or "")
        if checks_text:
            argv.extend(["--checks-text", checks_text])
        return _run_atom_main(pr_review.main, argv)

    if atom == "pr_merge":
        assert repo and pr_number is not None
        from lokay.config import load_config
        from lokay.merge_policy import decide_auto_merge

        merge_cfg = load_config(
            str(inputs.get("config_path") or inputs.get("config") or "") or None
        )
        checks = up.get("pr_checks") or {}
        review = up.get("pr_review") or {}
        # Trusted auto-merge gate (fail closed). Pending → waiting; red → repair;
        # secrets / needs_human / escalated needs-review never merge.
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
        argv = [*cfg, *live, "--repo", repo, "--pr", str(pr_number)]
        if issue_number is not None:
            argv.extend(["--issue", str(issue_number)])
        return _run_atom_main(pr_merge.main, argv)

    if atom == "close_issue":
        assert repo
        if inputs.get("keep_issue_open"):
            return {"ok": True, "skipped": True, "reason": "self_repair_validation_pending"}
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
            inputs.get("comment")
            or f"Closed by Lokay after merging PR #{pr_number}."
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
        # clear/merged only after a real (or planned) merge in pr_triage.
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
        argv = [
            *cfg,
            *live,
            "--repo",
            repo,
            "--issue",
            str(issue_number),
            "--stage",
            stage,
        ]
        if inputs.get("receipt"):
            argv.append("--receipt")
        comment = str(inputs.get("comment") or "").strip()
        if comment:
            argv.extend(["--comment", comment])
        return _run_atom_main(stage_label.main, argv)


    return None
