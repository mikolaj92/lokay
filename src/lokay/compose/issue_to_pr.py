"""Composer: chain atomic processes for one issue. No reimplementation of git/gh."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import tempfile
from pathlib import Path
from typing import Any, Callable

from lokay.envelope import emit_exit, err, ok
from lokay.models import Issue
from lokay.proc import (
    assign_issue as p_assign,
    commit_all as p_commit,
    get_issue as p_get,
    list_prs as p_list_prs,
    make_branch as p_branch,
    pr_create as p_pr_create,
    pr_label as p_label,
    push_branch as p_push,
    run_agent as p_agent,
    worktree_add as p_wt,
)
from lokay.proc._common import add_config_live, load_cfg
from lokay.prompts import issue_fix_prompt, pr_body
from lokay.state import append_event


def _run(main_fn: Callable[..., int], argv: list[str]) -> dict[str, Any]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = main_fn(argv)
    lines = buf.getvalue().strip().splitlines()
    if not lines:
        return {"ok": False, "error": "empty process output", "_exit": code}
    data = json.loads(lines[-1])
    data["_exit"] = code
    return data


def compose_issue_to_pr(
    *,
    config_path: str | None,
    repo: str,
    issue_number: int,
    live: bool,
) -> dict[str, Any]:
    cfg = load_cfg(argparse.Namespace(config=config_path))
    steps: list[dict[str, Any]] = []
    live_flag = ["--live"] if live else []
    cfg_flag = ["--config", config_path] if config_path else []

    if live and cfg.mode != "live":
        return err("refusing live compose while config mode is not live")

    # 0 get issue (read always hits network unless offline)
    s = _run(p_get.main, [*cfg_flag, "--repo", repo, "--issue", str(issue_number)])
    steps.append({"step": "get_issue", **s})
    if not s.get("ok"):
        return err("get_issue failed", steps=steps)
    issue = Issue.from_dict(s["issue"])

    # 1 assign
    s = _run(
        p_assign.main,
        [*cfg_flag, *live_flag, "--repo", repo, "--issue", str(issue_number)],
    )
    steps.append({"step": "assign_issue", **s})

    # 2 branch
    s = _run(
        p_branch.main,
        [
            "--prefix",
            cfg.branch_prefix,
            "--repo",
            repo,
            "--issue",
            str(issue_number),
            "--title",
            issue.title,
        ],
    )
    steps.append({"step": "make_branch", **s})
    if not s.get("ok"):
        return err("make_branch failed", steps=steps)
    branch = s["branch"]

    # 3 worktree
    s = _run(p_wt.main, [*cfg_flag, *live_flag, "--repo", repo, "--branch", branch])
    steps.append({"step": "worktree_add", **s})
    if not s.get("ok"):
        return err("worktree_add failed", steps=steps)
    worktree = s["worktree"]

    # 4 agent
    prompt = issue_fix_prompt(issue, branch=branch)
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
        fh.write(prompt)
        prompt_path = fh.name
    s = _run(
        p_agent.main,
        [*cfg_flag, *live_flag, "--worktree", worktree, "--prompt-file", prompt_path],
    )
    steps.append({"step": "run_agent", **s})
    Path(prompt_path).unlink(missing_ok=True)
    if s.get("status") == "failed":
        return err("agent failed", steps=steps)

    # 5 commit
    msg = f"fix: {repo}#{issue_number} {issue.title[:60]}"
    s = _run(p_commit.main, [*live_flag, "--worktree", worktree, "--message", msg])
    steps.append({"step": "commit_all", **s})

    # 6 push
    s = _run(p_push.main, [*live_flag, "--worktree", worktree, "--branch", branch])
    steps.append({"step": "push", **s})
    if live and not s.get("ok"):
        return err("push failed", steps=steps)

    # 7 PR
    summary = ""
    for step in reversed(steps):
        if step.get("step") == "run_agent":
            summary = str(step.get("stdout_tail") or step.get("status") or "")
            break
    body = pr_body(issue, agent_summary=summary)
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
        fh.write(body)
        body_path = fh.name
    title = f"fix: {repo}#{issue_number} {issue.title[:72]}"
    s = _run(
        p_pr_create.main,
        [
            *cfg_flag,
            *live_flag,
            "--repo",
            repo,
            "--title",
            title,
            "--body-file",
            body_path,
            "--head",
            branch,
        ],
    )
    steps.append({"step": "pr_create", **s})
    Path(body_path).unlink(missing_ok=True)

    # 8 labels
    s_list = _run(p_list_prs.main, [*cfg_flag, "--repo", repo])
    steps.append({"step": "list_prs", **s_list})
    pr_number = None
    for pr in s_list.get("prs") or []:
        if pr.get("head_ref") == branch:
            pr_number = pr.get("number")
            break
    if pr_number is not None:
        s = _run(
            p_label.main,
            [*cfg_flag, *live_flag, "--repo", repo, "--pr", str(pr_number)],
        )
        steps.append({"step": "pr_label", **s})

    result = ok(
        kind="issue_to_pr",
        planned=not live,
        repo=repo,
        issue=issue_number,
        branch=branch,
        worktree=worktree,
        pr_number=pr_number,
        agent=cfg.agent,
        steps=steps,
    )
    append_event(cfg.state_path, result)
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-issue-to-pr")
    add_config_live(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--issue", required=True, type=int)
    args = p.parse_args(argv)
    return emit_exit(
        compose_issue_to_pr(
            config_path=args.config,
            repo=args.repo,
            issue_number=args.issue,
            live=bool(args.live),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
