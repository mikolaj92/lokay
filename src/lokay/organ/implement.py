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


def handle_implement(atom: str, inputs: dict[str, Any], up: dict[str, dict[str, Any]], ctx: dict[str, Any]) -> dict[str, Any] | None:
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

    if atom == "assign_issue":
        assert repo and issue_number is not None
        return _run_atom_main(
            assign_issue.main,
            [*cfg, *live, "--repo", repo, "--issue", str(issue_number)],
        )

    if atom == "make_branch":
        issue_obj = up.get("get_issue", {}).get("issue") or {}
        title = str(issue_obj.get("title") or inputs.get("title") or "")
        prefix = str(inputs.get("branch_prefix") or "ai/fix")
        assert repo and issue_number is not None
        return _run_atom_main(
            make_branch.main,
            [
                "--prefix",
                prefix,
                "--repo",
                repo,
                "--issue",
                str(issue_number),
                "--title",
                title,
            ],
        )

    if atom == "worktree_add":
        branch = str(
            up.get("make_branch", {}).get("branch")
            or inputs.get("branch")
            or ""
        )
        assert repo and branch
        # issue_to_pr has make_branch upstream → reset onto origin/main.
        # pr_repair / pr_triage reuse the existing PR branch tip (inputs.branch).
        argv = [*cfg, *live, "--repo", repo, "--branch", branch]
        if "make_branch" in up:
            argv.append("--reset-base")
        return _run_atom_main(worktree_add.main, argv)

    if atom == "plan_issue":
        worktree = str(up.get("worktree_add", {}).get("worktree") or inputs.get("worktree") or "")
        issue_raw = up.get("get_issue", {}).get("issue") or {}
        assert worktree
        if not issue_raw and issue_number is not None and repo:
            issue_raw = {
                "repo": repo,
                "number": issue_number,
                "title": str(inputs.get("title") or ""),
                "body": str(inputs.get("body") or ""),
                "labels": [],
                "assignees": [],
                "url": str(inputs.get("url") or ""),
            }
        assert issue_raw
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
            json.dump(issue_raw, fh, ensure_ascii=False)
            issue_path = fh.name
        try:
            return _run_atom_main(
                plan_issue.main,
                [*cfg, *live, "--worktree", worktree, "--issue-json", issue_path],
            )
        finally:
            Path(issue_path).unlink(missing_ok=True)

    if atom == "localize":
        worktree = str(up.get("worktree_add", {}).get("worktree") or inputs.get("worktree") or "")
        assert worktree
        argv = [*cfg, *live, "--worktree", worktree]
        issue_path = ""
        checks_path = ""
        try:
            if repair_mode:
                checks_text = str(
                    up.get("pr_checks", {}).get("text")
                    or inputs.get("checks_text")
                    or ""
                )
                review_text = json.dumps(
                    inputs.get("review") or {}, ensure_ascii=False, sort_keys=True
                )
                seed = "\n\n".join(
                    part for part in (checks_text, review_text) if part and str(part).strip()
                )
                if not seed.strip():
                    seed = f"repair PR #{pr_number} in {repo}" if pr_number else f"repair in {repo}"
                with tempfile.NamedTemporaryFile(
                    "w", suffix=".md", delete=False, encoding="utf-8"
                ) as fh:
                    fh.write(seed)
                    checks_path = fh.name
                argv.extend(["--seed-file", checks_path])
                if repo:
                    argv.extend(["--repo", repo])
            else:
                issue_raw = up.get("get_issue", {}).get("issue") or {}
                if not issue_raw and issue_number is not None and repo:
                    issue_raw = {
                        "repo": repo,
                        "number": issue_number,
                        "title": str(inputs.get("title") or ""),
                        "body": str(inputs.get("body") or ""),
                        "labels": [],
                        "assignees": [],
                        "url": str(inputs.get("url") or ""),
                    }
                assert issue_raw
                with tempfile.NamedTemporaryFile(
                    "w", suffix=".json", delete=False, encoding="utf-8"
                ) as fh:
                    json.dump(issue_raw, fh, ensure_ascii=False)
                    issue_path = fh.name
                argv.extend(["--issue-json", issue_path])
            return _run_atom_main(localize.main, argv)
        finally:
            if issue_path:
                Path(issue_path).unlink(missing_ok=True)
            if checks_path:
                Path(checks_path).unlink(missing_ok=True)


    if atom == "cycle_start":
        assert repo and issue_number is not None
        return _run_atom_main(
            cycle_start.main, ["--repo", repo, "--issue", str(issue_number)]
        )

    if atom == "cycle_end":
        assert repo and issue_number is not None
        return _run_atom_main(
            cycle_end.main, ["--repo", repo, "--issue", str(issue_number)]
        )

    if atom == "pi_budget":
        pid = int(inputs.get("pid") or 0)
        budget = int(inputs.get("budget") or 480)
        return _run_atom_main(
            pi_budget.main, ["--pid", str(pid), "--budget", str(budget)]
        )


    return None
