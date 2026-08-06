"""Composer: issue → agent → PR.

Order matches Fala path `issue_to_pr`. Default engine: Unix atomics
(LOKAY_USE_FALA=1 to force Fala host).
"""

from __future__ import annotations

import argparse
from typing import Any

from lokay.compose._atoms import run_atom, unlink_quiet, use_fala, write_temp
from lokay.config import load_config
from lokay.envelope import emit_exit
from lokay.models import Issue
from lokay.proc import assign_issue as p_assign
from lokay.proc import commit_all as p_commit
from lokay.proc import get_issue as p_get
from lokay.proc import list_prs as p_list_prs
from lokay.proc import make_branch as p_branch
from lokay.proc import pr_create as p_pr_create
from lokay.proc import pr_label as p_pr_label
from lokay.proc import push_branch as p_push
from lokay.proc import run_agent as p_agent
from lokay.proc import worktree_add as p_worktree
from lokay.proc._common import add_config_live
from lokay.prompts import issue_fix_prompt, pr_body
from lokay.state import append_event


def _atomic_issue_to_pr(
    *,
    config_path: str | None,
    repo: str,
    issue_number: int,
    live: bool,
) -> dict[str, Any]:
    cfg = load_config(config_path)
    cfg_flag = ["--config", config_path] if config_path else []
    live_flag = ["--live"] if live else []
    steps: list[dict[str, Any]] = []

    got = run_atom(
        p_get.main,
        [*cfg_flag, "--repo", repo, "--issue", str(issue_number)],
    )
    steps.append({"step": "get_issue", **got})
    if not got.get("ok") or not got.get("issue"):
        return {"ok": False, "error": got.get("error") or "get_issue failed", "engine": "atoms", "steps": steps}
    issue = Issue.from_dict(got["issue"])

    assigned = run_atom(
        p_assign.main,
        [*cfg_flag, *live_flag, "--repo", repo, "--issue", str(issue_number)],
    )
    steps.append({"step": "assign_issue", **assigned})

    branch_res = run_atom(
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
    steps.append({"step": "make_branch", **branch_res})
    if not branch_res.get("ok"):
        return {"ok": False, "error": "make_branch failed", "engine": "atoms", "steps": steps}
    branch = str(branch_res["branch"])

    # Always reset onto origin/main so re-implement after a closed CONFLICTING
    # PR does not reuse a stale tip under the same deterministic branch name.
    wt = run_atom(
        p_worktree.main,
        [
            *cfg_flag,
            *live_flag,
            "--repo",
            repo,
            "--branch",
            branch,
            "--reset-base",
        ],
    )
    steps.append({"step": "worktree_add", **wt})
    if not wt.get("ok"):
        return {"ok": False, "error": wt.get("error") or "worktree_add failed", "engine": "atoms", "steps": steps}
    worktree = str(wt.get("worktree") or "")

    prompt = issue_fix_prompt(issue, branch=branch)
    prompt_path = write_temp(prompt)
    try:
        agent = run_atom(
            p_agent.main,
            [*cfg_flag, *live_flag, "--worktree", worktree, "--prompt-file", prompt_path],
        )
    finally:
        unlink_quiet(prompt_path)
    steps.append({"step": "run_agent", **agent})
    if not agent.get("ok") or agent.get("status") == "failed":
        return {"ok": False, "error": "run_agent failed", "engine": "atoms", "steps": steps}

    msg = f"fix: {repo}#{issue_number} {issue.title[:60]}"
    committed = run_atom(
        p_commit.main,
        [*live_flag, "--worktree", worktree, "--message", msg],
    )
    steps.append({"step": "commit_all", **committed})
    if not committed.get("ok"):
        return {"ok": False, "error": "commit_all failed", "engine": "atoms", "steps": steps}

    pushed = run_atom(
        p_push.main,
        [*live_flag, "--worktree", worktree, "--branch", branch],
    )
    steps.append({"step": "push", **pushed})
    if not pushed.get("ok"):
        return {"ok": False, "error": pushed.get("error") or "push failed", "engine": "atoms", "steps": steps}

    body = pr_body(issue, agent_summary=str(agent.get("stdout_tail") or agent.get("status") or ""))
    body_path = write_temp(body)
    title = f"fix: {repo}#{issue.number} {issue.title[:72]}"
    try:
        created = run_atom(
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
    finally:
        unlink_quiet(body_path)
    steps.append({"step": "pr_create", **created})
    if not created.get("ok"):
        return {"ok": False, "error": created.get("error") or "pr_create failed", "engine": "atoms", "steps": steps}

    listed = run_atom(p_list_prs.main, [*cfg_flag, "--repo", repo])
    steps.append({"step": "list_prs", **listed})
    pr_number = None
    for pr in listed.get("prs") or []:
        if pr.get("head_ref") == branch:
            pr_number = pr.get("number")
            break
    if pr_number is not None:
        labeled = run_atom(
            p_pr_label.main,
            [*cfg_flag, *live_flag, "--repo", repo, "--pr", str(pr_number)],
        )
        steps.append({"step": "pr_label", **labeled})

    return {
        "ok": True,
        "engine": "atoms",
        "repo": repo,
        "issue": issue_number,
        "branch": branch,
        "pr": pr_number,
        "steps": steps,
    }


def compose_issue_to_pr(
    *,
    config_path: str | None,
    repo: str,
    issue_number: int,
    live: bool,
) -> dict:
    if live:
        cfg = load_config(config_path)
        if cfg.mode != "live":
            return {
                "ok": False,
                "error": "refusing live compose while config mode is not live",
            }

    if use_fala():
        from lokay.graph_run import run_path

        result = run_path(
            path_id="issue_to_pr",
            repo=repo,
            issue=issue_number,
            config_path=config_path,
            live=live,
        )
        result["kind"] = "issue_to_pr"
        result["engine"] = "fala"
        result["planned"] = not live
    else:
        result = _atomic_issue_to_pr(
            config_path=config_path,
            repo=repo,
            issue_number=issue_number,
            live=live,
        )
        result["kind"] = "issue_to_pr"
        result["planned"] = not live

    try:
        cfg = load_config(config_path)
        append_event(cfg.state_path, result)
    except Exception:
        pass
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-issue-to-pr")
    add_config_live(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--issue", required=True, type=int)
    args = p.parse_args(argv)
    payload = compose_issue_to_pr(
        config_path=args.config,
        repo=args.repo,
        issue_number=args.issue,
        live=bool(args.live),
    )
    return emit_exit(payload if "ok" in payload else {**payload, "ok": bool(payload.get("ok"))})


if __name__ == "__main__":
    raise SystemExit(main())
