"""Fala organ routing — one job family per module."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from lokay.models import Issue
from lokay.organ.agent_evidence import head_has_on_goal_src
from lokay.organ.common import (
    _issue_no_longer_open,
    _localize_paths,
    _require_push,
    _require_real_diff,
    _require_test_local,
    _resume_after_timeout,
    _run_atom_main,
    _test_local_ok,
)
from lokay.prompts import (
    issue_fix_prompt,
    local_test_repair_prompt,
    pr_body,
    repair_pr_prompt,
)


def handle_agent(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    from lokay.proc import (
        assert_real_diff,
        commit_all,
        get_issue,
        pr_create,
        push_branch,
        rebase_onto_base,
        run_agent,
        test_local,
    )
    from lokay.git_commit import branch_ahead_of_upstream
    from lokay.proc._common import runner

    cfg = ctx["cfg"]
    live = ctx["live"]
    repo = ctx["repo"]
    repo_flags = ["--repo", repo] if repo else []
    issue_number = ctx["issue_number"]
    pr_number = ctx["pr_number"]
    repair_mode = ctx["repair_mode"]
    branch = ctx["branch"]

    import lokay.fala_organ as _fo

    _run_atom_main = _fo._run_atom_main
    branch_ahead_of_upstream = getattr(_fo, "branch_ahead_of_upstream", None)
    if branch_ahead_of_upstream is None:
        from lokay.git_commit import branch_ahead_of_upstream

    if atom == "run_agent":
        worktree = str(up.get("worktree_add", {}).get("worktree") or "")
        branch = str(
            up.get("make_branch", {}).get("branch")
            or inputs.get("branch")
            or up.get("worktree_add", {}).get("branch")
            or ""
        )
        assert worktree
        if "localize" not in up:
            return {
                "ok": False,
                "error": "refusing run_agent: localize conduction missing",
                "reason": "localize_missing",
            }
        paths = _localize_paths(up)
        if not paths:
            return {
                "ok": False,
                "error": "refusing run_agent: localize produced no edit paths",
                "reason": "localize_empty",
                "localize": up.get("localize") or {},
            }
        if repair_mode:
            assert pr_number is not None and branch
            checks_text = str(
                up.get("pr_checks", {}).get("text") or inputs.get("checks_text") or ""
            )
            prompt = repair_pr_prompt(
                repo=repo,
                pr_number=pr_number,
                branch=branch,
                checks_text=checks_text,
                review_text=json.dumps(
                    inputs.get("review") or {}, ensure_ascii=False, sort_keys=True
                ),
                paths=paths,
            )
        else:
            issue_raw = up.get("get_issue", {}).get("issue") or {}
            issue = Issue.from_dict(issue_raw) if issue_raw else None
            assert issue is not None
            prompt = issue_fix_prompt(issue, branch=branch, paths=paths)
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

    if atom == "repair_agent":
        if repair_mode:
            return {
                "ok": False,
                "error": "refusing: repair_agent is issue_to_pr-only",
                "reason": "repair_agent_not_allowed",
            }
        worktree = str(up.get("worktree_add", {}).get("worktree") or "")
        first = up.get("test_local") or {}
        assert worktree
        log_text = "\n".join(
            text
            for text in (
                str(first.get("stdout_tail") or ""),
                str(first.get("stderr_tail") or ""),
            )
            if text.strip()
        ) or str(first.get("error") or "")
        issue_raw = up.get("get_issue", {}).get("issue") or {}
        prompt = local_test_repair_prompt(
            repo=repo,
            branch=branch,
            issue_number=issue_number,
            issue_title=str(issue_raw.get("title") or ""),
            log_text=log_text,
        )
        with tempfile.NamedTemporaryFile(
            "w", suffix=".md", delete=False, encoding="utf-8"
        ) as fh:
            fh.write(prompt)
            prompt_path = fh.name
        try:
            out = _run_atom_main(
                run_agent.main,
                [*cfg, *live, "--worktree", worktree, "--prompt-file", prompt_path],
            )
        finally:
            Path(prompt_path).unlink(missing_ok=True)
        if isinstance(out, dict):
            out["attempted"] = True
        return out

    return None
