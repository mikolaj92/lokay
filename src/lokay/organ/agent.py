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
from lokay.prompts import issue_fix_prompt, local_test_repair_prompt, pr_body, repair_pr_prompt


def handle_agent(atom: str, inputs: dict[str, Any], up: dict[str, dict[str, Any]], ctx: dict[str, Any]) -> dict[str, Any] | None:
    from lokay.proc import (
        assert_real_diff, commit_all, get_issue, pr_create, push_branch,
        rebase_onto_base, run_agent, test_local,
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
                up.get("pr_checks", {}).get("text")
                or inputs.get("checks_text")
                or ""
            )
            prompt = repair_pr_prompt(
                repo=repo,
                pr_number=pr_number,
                branch=branch,
                checks_text=checks_text,
                review_text=json.dumps(inputs.get("review") or {}, ensure_ascii=False, sort_keys=True),
                paths=paths,
            )
        else:
            issue_raw = up.get("get_issue", {}).get("issue") or {}
            issue = Issue.from_dict(issue_raw) if issue_raw else None
            assert issue is not None
            prompt = issue_fix_prompt(issue, branch=branch, paths=paths)
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
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
        assert worktree
        run_env = up.get("run_agent") or {}
        localized = run_env.get("localize")
        if localized is None:
            localized = up.get("localize")
        if str(run_env.get("reason") or "") in {"localize_empty", "localize_missing"} or (
            isinstance(localized, dict)
            and not _localize_paths({"localize": localized})
        ):
            return {
                "ok": False,
                "error": "refusing repair_agent: localize produced no edit paths",
                "reason": "localize_empty",
                "localize": localized or {},
            }
        first = up.get("test_local")
        if first is None:
            return {
                "ok": False,
                "error": "refusing: test_local conduction missing",
                "reason": "test_local_missing",
            }
        if head_has_on_goal_src(worktree, localized):
            return {
                "ok": True,
                "skipped": True,
                "reason": "head_has_on_goal_src",
            }
        if _test_local_ok(first):
            run_env = up.get("run_agent") or {}
            timed_out = bool(run_env.get("timed_out")) or str(
                run_env.get("reason") or ""
            ) == "timeout"
            if not timed_out:
                return {"ok": True, "skipped": True, "reason": "test_local_ok"}
            return _resume_after_timeout(
                run_agent_main=run_agent.main,
                assert_real_diff_main=assert_real_diff.main,
                commit_all_main=commit_all.main,
                cfg=cfg,
                live=live,
                inputs=inputs,
                worktree=worktree,
                repo=repo,
                branch=branch,
                issue_number=issue_number,
                issue_raw=up.get("get_issue", {}).get("issue") or {},
                get_issue_main=get_issue.main,
            )
        log_text = "\n".join(
            tail
            for tail in (
                str(first.get("stdout_tail") or ""),
                str(first.get("stderr_tail") or ""),
            )
            if tail.strip()
        ) or str(first.get("error") or "")
        issue_raw = up.get("get_issue", {}).get("issue") or {}
        prompt = local_test_repair_prompt(
            repo=repo,
            branch=branch,
            issue_number=issue_number,
            issue_title=str(issue_raw.get("title") or ""),
            log_text=log_text,
        )
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
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

    if atom == "test_local_recheck":
        worktree = str(up.get("worktree_add", {}).get("worktree") or "")
        assert worktree
        first = up.get("test_local")
        if first is None:
            return {
                "ok": False,
                "error": "refusing: test_local conduction missing",
                "reason": "test_local_missing",
            }
        if _test_local_ok(first):
            return {"ok": True, "skipped": True, "reason": "test_local_ok"}
        repair = up.get("repair_agent") or {}
        if repair.get("ok") is False:
            return {
                "ok": False,
                "error": str(repair.get("error") or "repair agent failed"),
                "reason": "repair_agent_failed",
            }
        if inputs.get("live"):
            unpublished = branch_ahead_of_upstream(
                runner(), Path(worktree), live=True
            ) > 0
            committed = bool(up.get("commit_all", {}).get("committed"))
            if not (committed or unpublished):
                return {
                    "ok": False,
                    "error": "refusing recheck: repair patch produced no commit",
                    "reason": "zero_diff",
                }
        argv = ["--worktree", worktree]
        if inputs.get("changed_scope"):
            argv.append("--changed-scope")
        out = _run_atom_main(test_local.main, argv)
        if isinstance(out, dict):
            if out.get("ok") is False and not out.get("skipped"):
                out = {
                    "ok": False,
                    "reason": "local_repair_exhausted",
                    "recheck": True,
                    **{
                        k: v
                        for k, v in out.items()
                        if k not in {"ok", "reason", "recheck"}
                    },
                }
            else:
                out["recheck"] = True
        return out

    if atom == "commit_all":
        worktree = str(up.get("worktree_add", {}).get("worktree") or "")
        assert worktree
        issue_body = str(
            up.get("get_issue", {}).get("issue", {}).get("body") or ""
        )
        gate = _run_atom_main(
            assert_real_diff.main,
            ["--worktree", worktree, "--issue-body", issue_body],
        )
        if not (isinstance(gate, dict) and gate.get("real") is True):
            return {
                "ok": False,
                "error": str((gate or {}).get("error") or "refusing commit: not a real diff"),
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
        return _run_atom_main(rebase_onto_base.main, [*cfg, *live, "--worktree", worktree])

    if atom == "test_local":
        worktree = str(up.get("worktree_add", {}).get("worktree") or "")
        assert worktree
        argv = ["--worktree", worktree]
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
        issue_body = str(
            up.get("get_issue", {}).get("issue", {}).get("body") or ""
        )
        assert worktree
        return _run_atom_main(
            assert_real_diff.main,
            ["--worktree", worktree, "--issue-body", issue_body],
        )

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
        committed = up.get("commit_all", {}).get("committed")
        if inputs.get("live") and committed is not True:
            unpublished = branch_ahead_of_upstream(
                runner(), Path(worktree), live=True
            ) > 0
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
            [*cfg, *live, "--worktree", worktree, "--branch", branch],
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
        body = pr_body(issue, agent_summary=summary, incident_fingerprint=str(inputs.get("incident_fingerprint") or ""))
        title = f"fix: {repo}#{issue.number} {issue.title[:72]}"
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
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
                    *(["--issue", str(issue_number)] if issue_number is not None else []),
                ],
            )
        finally:
            Path(body_path).unlink(missing_ok=True)

    return None
