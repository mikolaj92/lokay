"""Fala organ routing — one job family per module."""

from __future__ import annotations

from typing import Any


def handle_implement(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    from lokay.proc import (
        assign_issue,
        cycle_end,
        cycle_start,
        make_branch,
        pi_budget,
        worktree_add,
    )

    cfg = ctx["cfg"]
    live = ctx["live"]
    repo = ctx["repo"]
    issue_number = ctx["issue_number"]
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
            up.get("make_branch", {}).get("branch") or inputs.get("branch") or ""
        )
        assert repo and branch
        # issue_to_pr has make_branch upstream → reset onto origin/main.
        # pr_repair / pr_triage reuse the existing PR branch tip (inputs.branch).
        argv = [*cfg, *live, "--repo", repo, "--branch", branch]
        if "make_branch" in up:
            argv.append("--reset-base")
        return _run_atom_main(worktree_add.main, argv)

    if atom == "plan_issue":
        worktree = str(
            up.get("worktree_add", {}).get("worktree") or inputs.get("worktree") or ""
        )
        issue_raw = up.get("get_issue", {}).get("issue") or {}
        assert worktree and issue_raw
        from lokay.proc.plan_issue_subflow import run

        return run(
            config_path=str(inputs.get("config_path") or "") or None,
            live=bool(inputs.get("live")),
            worktree=worktree,
            issue_raw=dict(issue_raw),
            repo=str(issue_raw.get("repo") or repo),
        )

    if atom == "localize":
        from lokay.proc.localize_execution_subflow import run

        worktree = str(
            up.get("worktree_add", {}).get("worktree") or inputs.get("worktree") or ""
        )
        issue_raw = dict(up.get("get_issue", {}).get("issue") or {})
        if not issue_raw and issue_number is not None and repo:
            issue_raw = {
                "repo": repo,
                "number": issue_number,
                "title": str(inputs.get("title") or ""),
                "body": str(inputs.get("body") or ""),
            }
        checks_text = (
            str(up.get("pr_checks", {}).get("text") or inputs.get("checks_text") or "")
            if repair_mode
            else ""
        )
        return run(
            config_path=str(inputs.get("config_path") or "") or None,
            live=bool(inputs.get("live")),
            extra_inputs={
                "worktree": worktree,
                "repo": repo,
                "issue_raw": issue_raw,
                "plan": up.get("plan_issue") or {},
                "checks_text": checks_text,
                "review": inputs.get("review") or {},
                "extra_paths": list(inputs.get("extra_paths") or []),
                "max_paths": int(inputs.get("max_paths") or 40),
                "rel_path": str(inputs.get("rel_path") or ".lokay/localize.json"),
            },
        )

    if atom == "relocalize_off_goal":
        from lokay.proc.relocalize_off_goal_subflow import run

        worktree = str(up.get("worktree_add", {}).get("worktree") or "")
        return run(
            config_path=str(inputs.get("config_path") or "") or None,
            live=bool(inputs.get("live")),
            extra_inputs={
                "worktree": worktree,
                "base": str(inputs.get("base") or "origin/main"),
                "repo": repo,
                "issue_raw": dict(up.get("get_issue", {}).get("issue") or {}),
            },
        )

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
        budget = int(inputs.get("budget") or 1800)
        return _run_atom_main(
            pi_budget.main, ["--pid", str(pid), "--budget", str(budget)]
        )

    return None
