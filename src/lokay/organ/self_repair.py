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


def handle_self_repair(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    from lokay.proc import (
        assign_issue,
        close_issue,
        commit_all,
        closeout_prs,
        compute_health,
        cycle_end,
        cycle_start,
        dispatch_implement,
        dispatch_triage,
        factory_begin,
        factory_tick,
        get_issue,
        host_ff,
        list_prs,
        make_branch,
        plan_issue,
        localize,
        pi_budget,
        plan_pass,
        pr_checks,
        pr_create,
        pr_label,
        pr_merge,
        push_branch,
        record_pass,
        recovery_begin,
        recovery_incident,
        recovery_mill,
        recovery_observe,
        recovery_record,
        recovery_run_self_repair,
        resolve_conflicts,
        run_agent,
        select_implement,
        queue_conflict,
        stage_label,
        survey_inbox,
        survey_prs,
        survey_ready,
        survey_repos,
        test_local,
        worktree_add,
        assert_real_diff,
        self_repair_activate,
        self_repair_close,
        self_repair_prepare,
        self_repair_preflight,
        self_repair_push_main,
        self_repair_validate,
    )
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
    known = False

    if atom == "summarize_self_repair":
        from lokay.proc.summarize_self_repair import summarize

        return summarize(
            preflight=up.get("self_repair_preflight") or {},
            push=up.get("self_repair_push_main") or {},
            activate=up.get("self_repair_activate") or {},
            close=up.get("self_repair_close") or {},
        )

    if atom == "self_repair_prepare":
        from lokay.proc.self_repair_prepare_subflow import run

        fingerprint = str(inputs.get("fingerprint") or "")
        assert fingerprint
        return run(
            fingerprint=fingerprint,
            config_path=str(inputs.get("config_path") or "") or None,
            live=bool(inputs.get("live")),
        )

    if atom == "self_repair_run_agent":
        prepared = up.get("self_repair_prepare", {})
        if prepared.get("already_on_main") or prepared.get("resumed"):
            return {
                "ok": True,
                "skipped": True,
                "reason": (
                    "already_on_main"
                    if prepared.get("already_on_main")
                    else "resume_existing_candidate"
                ),
                "commit": prepared.get("commit") or prepared.get("candidate_commit"),
            }
        worktree = str(prepared.get("worktree") or "")
        issue_raw = inputs.get("incident") or {}
        issue = Issue.from_dict(issue_raw) if isinstance(issue_raw, dict) else None
        fingerprint = str(inputs.get("fingerprint") or "")
        assert worktree and issue is not None and fingerprint
        prompt = self_repair_prompt(
            issue=issue,
            fingerprint=fingerprint,
            evidence=str(inputs.get("failure_evidence") or ""),
        )
        with tempfile.NamedTemporaryFile(
            "w", suffix=".md", delete=False, encoding="utf-8"
        ) as fh:
            fh.write(prompt)
            prompt_path = fh.name
        try:
            return _run_atom_main(
                run_agent.main,
                [*cfg, *live, "--worktree", worktree, "--prompt-file", prompt_path],
            )
        finally:
            Path(prompt_path).unlink(missing_ok=True)

    if atom == "self_repair_validate":
        prepared = up.get("self_repair_prepare", {})
        if prepared.get("already_on_main"):
            return {
                "ok": True,
                "skipped": True,
                "validated": True,
                "reason": "already_on_main",
            }
        committed = up.get("self_repair_commit", {})
        worktree = str(prepared.get("worktree") or "")
        base_sha = str(prepared.get("base_sha") or "")
        fingerprint = str(inputs.get("fingerprint") or "")
        assert worktree and base_sha and fingerprint and committed.get("commit")
        return _run_atom_main(
            self_repair_validate.main,
            [
                "--worktree",
                worktree,
                "--base-sha",
                base_sha,
                "--expected-subject",
                f"self-repair: {fingerprint}",
                "--expected-commit",
                str(committed["commit"]),
            ],
        )

    if atom == "self_repair_commit":
        prepared = up.get("self_repair_prepare", {})
        if prepared.get("already_on_main") or prepared.get("candidate_commit"):
            return {
                "ok": True,
                "skipped": True,
                "reason": (
                    "already_on_main"
                    if prepared.get("already_on_main")
                    else "resume_committed_candidate"
                ),
                "commit": prepared.get("commit") or prepared.get("candidate_commit"),
            }
        worktree = str(prepared.get("worktree") or "")
        fingerprint = str(inputs.get("fingerprint") or "")
        assert worktree and fingerprint
        return _run_atom_main(
            commit_all.main,
            [
                *cfg,
                *live,
                "--worktree",
                worktree,
                "--message",
                f"self-repair: {fingerprint}",
            ],
        )

    if atom == "self_repair_push_main":
        prepared = up.get("self_repair_prepare", {})
        if prepared.get("already_on_main"):
            return {
                "ok": True,
                "skipped": True,
                "reason": "already_on_main",
                "commit": prepared.get("commit"),
                "pushed": False,
            }
        validated = up.get("self_repair_validate", {})
        committed = up.get("self_repair_commit", {})
        worktree = str(prepared.get("worktree") or "")
        base_sha = str(prepared.get("base_sha") or "")
        expected_commit = str(committed.get("commit") or "")
        validated_commit = str(validated.get("commit") or "")
        assert (
            worktree
            and base_sha
            and expected_commit
            and validated_commit == expected_commit
            and validated.get("validated") is True
        )
        return _run_atom_main(
            self_repair_push_main.main,
            [
                *cfg,
                *live,
                "--worktree",
                worktree,
                "--base-sha",
                base_sha,
                "--validated",
                "--expected-commit",
                validated_commit,
            ],
        )

    if atom == "self_repair_activate":
        prepared = up.get("self_repair_prepare", {})
        commit = str(
            up.get("self_repair_push_main", {}).get("commit")
            or prepared.get("commit")
            or ""
        )
        assert commit
        return _run_atom_main(
            self_repair_activate.main,
            [*cfg, *live, "--commit", commit],
        )

    if atom == "self_repair_preflight":
        activated = up.get("self_repair_activate", {})
        commit = str(activated.get("commit") or "")
        project = str(activated.get("path") or "")
        config_path = str(inputs.get("config_path") or inputs.get("config") or "")
        assert commit and project and config_path
        return _run_atom_main(
            self_repair_preflight.main,
            ["--config", config_path, "--project", project, "--commit", commit],
        )

    if atom == "self_repair_close":
        commit = str(up.get("self_repair_preflight", {}).get("commit") or "")
        assert issue_number is not None and commit
        return _run_atom_main(
            self_repair_close.main,
            [*cfg, *live, "--issue", str(issue_number), "--commit", commit],
        )

    return None
