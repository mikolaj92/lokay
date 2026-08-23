"""Fala bindings for physical commit, verification, and publication effects."""

from __future__ import annotations
import tempfile
from pathlib import Path
from typing import Any
from lokay.models import Issue
from lokay.organ.common import (
    _issue_no_longer_open,
    _require_push,
    _require_real_diff,
    _require_test_local,
    _run_atom_main,
)
from lokay.prompts import pr_body


def handle_publication(
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
        test_local,
    )
    from lokay.git_commit import branch_ahead_of_upstream
    from lokay.proc._common import runner

    cfg = ctx["cfg"]
    live = ctx["live"]
    repo = ctx["repo"]
    issue_number = ctx["issue_number"]
    pr_number = ctx["pr_number"]
    repair_mode = ctx["repair_mode"]
    branch = ctx["branch"]
    repo_flags = ["--repo", repo] if repo else []
    import lokay.fala_organ as _fo

    _run_atom_main = _fo._run_atom_main
    branch_ahead_of_upstream = getattr(
        _fo, "branch_ahead_of_upstream", branch_ahead_of_upstream
    )
    if atom == "commit_all":
        worktree = str(up.get("worktree_add", {}).get("worktree") or "")
        assert worktree
        gate = _run_atom_main(assert_real_diff.main, ["--worktree", worktree])
        if not (isinstance(gate, dict) and gate.get("real") is True):
            return {
                "ok": False,
                "error": str(
                    (gate or {}).get("error") or "refusing commit: not a real diff"
                ),
                "reason": str((gate or {}).get("reason") or "plan_only"),
                "committed": False,
                "kind": (gate or {}).get("kind"),
            }
        issue_raw = up.get("get_issue", {}).get("issue") or {}
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
        worktree = str(up.get("worktree_add", {}).get("worktree") or "")
        assert worktree
        return _run_atom_main(
            rebase_onto_base.main, [*cfg, *live, *repo_flags, "--worktree", worktree]
        )

    if atom == "test_local":
        worktree = str(up.get("worktree_add", {}).get("worktree") or "")
        assert worktree
        argv = [*repo_flags, "--worktree", worktree]
        if inputs.get("changed_scope"):
            argv.append("--changed-scope")
        out = _run_atom_main(test_local.main, argv)
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
        worktree = str(up.get("worktree_add", {}).get("worktree") or "")
        assert worktree
        return _run_atom_main(assert_real_diff.main, ["--worktree", worktree])

    if atom == "push":
        worktree = str(up.get("worktree_add", {}).get("worktree") or "")
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
                for name in ("commit_all", "commit_implementation", "commit_repair")
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
        issue_raw = up.get("get_issue", {}).get("issue") or {}
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
            return _run_atom_main(
                pr_create.main,
                [
                    *cfg,
                    *live,
                    "--repo",
                    repo,
                    "--title",
                    title,
                    "--body-file",
                    body_path,
                    "--head",
                    branch,
                    *(
                        ["--issue", str(issue_number)]
                        if issue_number is not None
                        else []
                    ),
                ],
            )
        finally:
            Path(body_path).unlink(missing_ok=True)

    return None
