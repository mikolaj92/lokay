"""Fala bindings for physical commit, verification, and publication effects."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from lokay.models import Issue
from lokay.organ.common import (
    _issue_no_longer_open,
    _issue_raw,
    _require_push,
    _require_real_diff,
    _require_test_local,
    _worktree_path,
)
from lokay.prompts import pr_body


def handle_publication(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    from lokay.proc import (
        commit_all,
        get_issue,
        push_branch,
        rebase_onto_base,
    )
    from lokay.proc._common import runner

    cfg = ctx["cfg"]
    live = ctx["live"]
    repo = ctx["repo"]
    issue_number = ctx["issue_number"]
    pr_number = ctx["pr_number"]
    repair_mode = ctx["repair_mode"]
    branch = ctx["branch"]
    repo_flags = ["--repo", repo] if repo else []
    from lokay.atom_runtime import run_atom_main
    from lokay.git_commit import branch_ahead_of_upstream as _branch_ahead

    _run_atom_main = ctx.get("run_atom_main") or run_atom_main
    branch_ahead_of_upstream = ctx.get("branch_ahead_of_upstream") or _branch_ahead
    if atom == "commit_all":
        worktree = _worktree_path(up, inputs)
        assert worktree
        gate = next(
            (
                up[name]
                for name in (
                    "assert_implementation_diff",
                    "assert_initial_repair_diff",
                    "assert_test_repair_diff",
                    "assert_repair_diff",
                    "assert_real_diff",
                )
                if name in up
            ),
            None,
        )
        if not isinstance(gate, dict) or gate.get("real") is not True:
            return {
                "ok": False,
                "error": str(
                    (gate or {}).get("error")
                    or "refusing commit: real-diff conduction missing or failed"
                ),
                "reason": str((gate or {}).get("reason") or "real_diff_missing"),
                "committed": False,
                "kind": (gate or {}).get("kind"),
            }
        issue_raw = _issue_raw(up, inputs)
        if repair_mode and pr_number is not None:
            msg = str(inputs.get("message") or f"repair: {repo} PR #{pr_number} checks")
        else:
            n = issue_raw.get("number", issue_number)
            title = str(issue_raw.get("title") or "")[:60]
            msg = str(inputs.get("message") or f"fix: {repo}#{n} {title}")
        assert worktree
        out = _run_atom_main(
            commit_all.main,
            [*cfg, *live, "--worktree", worktree, "--message", msg],
        )
        if (
            isinstance(out, dict)
            and out.get("ok") is True
            and inputs.get("live")
            and out.get("committed") is not True
            and branch_ahead_of_upstream(runner(), Path(worktree), live=True) > 0
        ):
            out["committed"] = True
            out["committed_by"] = "agent"
        return out

    if atom == "rebase_onto_base":
        worktree = _worktree_path(up, inputs)
        assert worktree
        return _run_atom_main(
            rebase_onto_base.main, [*cfg, *live, *repo_flags, "--worktree", worktree]
        )

    if atom in {"test_local", "test_local_execution"}:
        worktree = _worktree_path(up, inputs)
        assert worktree
        argv = [*repo_flags, "--worktree", worktree]
        if inputs.get("changed_scope"):
            argv.append("--changed-scope")
        from lokay.proc.test_local_execution_subflow import run

        out = run(
            worktree=worktree,
            changed_scope=bool(inputs.get("changed_scope")),
            repo=str(ctx.get("repo") or inputs.get("repo") or ""),
            issue=ctx.get("issue_number") or inputs.get("issue"),
        )
        if (
            inputs.get("record_red")
            and isinstance(out, dict)
            and out.get("ok") is False
            and not out.get("skipped")
        ):
            recorded = {
                "ok": True,
                "passed": False,
                "tested": True,
                "recorded_red": True,
                **{
                    k: v
                    for k, v in out.items()
                    if k not in {"ok", "passed", "tested", "recorded_red", "_exit"}
                },
                "_exit": 0,
            }
            return recorded
        return out

    if atom == "assert_real_diff":
        worktree = _worktree_path(up, inputs)
        assert worktree
        from lokay.proc.assert_real_diff_subflow import run as run_real_diff

        issue_raw = _issue_raw(up, inputs)
        return run_real_diff(
            worktree=worktree, issue_body=str(issue_raw.get("body") or ""), repo=repo
        )

    if atom == "push":
        worktree = _worktree_path(up, inputs)
        branch = str(
            up.get("make_branch", {}).get("branch")
            or inputs.get("branch")
            or up.get("worktree_add", {}).get("branch")
            or ""
        )
        assert worktree and branch
        refused = _require_test_local(up)
        if refused is not None:
            return refused
        refused = _require_real_diff(up)
        if refused is not None:
            return refused
        committed = next(
            (
                (up.get(name) or {}).get("committed")
                for name in (
                    "commit_all",
                    "commit_implementation",
                    "commit_repair",
                    "commit_initial_repair",
                    "commit_test_repair",
                )
                if up.get(name)
            ),
            None,
        )
        if inputs.get("live") and committed is not True:
            unpublished = (
                branch_ahead_of_upstream(runner(), Path(worktree), live=True) > 0
            )
            if not unpublished:
                return {
                    "ok": False,
                    "error": "refusing live push: no new commit to publish",
                    "reason": "zero_diff",
                    "committed": committed,
                    "worktree": worktree,
                    "branch": branch,
                }
        return _run_atom_main(
            push_branch.main,
            [*cfg, *live, *repo_flags, "--worktree", worktree, "--branch", branch],
        )

    if atom == "pr_create":
        refused = _issue_no_longer_open(
            up,
            cfg=cfg,
            live=live,
            repo=repo,
            issue_number=issue_number,
            run=_run_atom_main,
            get_issue_main=get_issue.main,
        )
        if refused is not None:
            return refused
        refused = _require_test_local(up)
        if refused is not None:
            return refused
        refused = _require_real_diff(up)
        if refused is not None:
            return refused
        refused = _require_push(up)
        if refused is not None:
            return refused
        branch = str(up.get("make_branch", {}).get("branch") or "")
        issue_raw = _issue_raw(up, inputs)
        issue = Issue.from_dict(issue_raw)
        agent = up.get("run_agent", {})
        summary = str(agent.get("stdout_tail") or agent.get("status") or "")
        body = pr_body(
            issue,
            agent_summary=summary,
            incident_fingerprint=str(inputs.get("incident_fingerprint") or ""),
        )
        title = f"fix: {repo}#{issue.number} {issue.title[:72]}"
        with tempfile.NamedTemporaryFile(
            "w", suffix=".md", delete=False, encoding="utf-8"
        ) as fh:
            fh.write(body)
            body_path = fh.name
        try:
            from lokay.proc.pr_create_subflow import run

            return run(
                config_path=str(inputs.get("config_path") or "") or None,
                live=bool(inputs.get("live")),
                repo=repo,
                issue=issue_number,
                title=title,
                body=Path(body_path).read_text(encoding="utf-8"),
                head=branch,
                base="main",
            )
        finally:
            Path(body_path).unlink(missing_ok=True)

    return None
