from __future__ import annotations

import os
from pathlib import Path

from lokay2.git import push, worktree_add
from lokay2.gh import pr_create
from lokay2.run import run_process
from lokay2.safety import untrusted_issue_block

DROP = ("GH_TOKEN", "GITHUB_TOKEN")


def child_env(base: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in base.items() if key not in DROP}


def _git(repo: Path, args: list[str]) -> str:
    proc = run_process(["git", *args], cwd=repo, timeout=30)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "").strip())
    return (proc.stdout or "").strip()


def build_code(worktree: Path, plan: str, title: str, body: str | None, env: dict[str, str]) -> dict:
    clean = child_env(env)
    proc = run_process(
        ["pi", "-p", "--provider", clean.get("LOKAY2_PROVIDER", ""), "--model", clean.get("LOKAY2_MODEL", ""), plan + "\n" + untrusted_issue_block(title, body)],
        cwd=worktree,
        env=clean,
        timeout=3600,
    )
    if proc.returncode != 0:
        return {"result": "failed", "artifact": ""}
    status = _git(worktree, ["status", "--porcelain"])
    if status:
        _git(worktree, ["add", "-A"])
        _git(worktree, ["commit", "-m", "lokay2 build"])
    log = _git(worktree, ["log", "--oneline", "origin/main..HEAD"])
    if not log:
        return {"result": "failed", "artifact": ""}
    return {"result": "done", "artifact": _git(worktree, ["rev-parse", "HEAD"])}


def build_publish(worktree: Path, branch: str, expected: str | None, repo_name: str, issue: int, title: str) -> dict:
    pushed = push(worktree, branch, expected)
    if pushed["result"] != "pushed":
        return {"result": pushed["result"], "pr": None, "sha": pushed.get("sha", "")}
    created = pr_create(repo_name, branch, title, "plan.md", issue)
    return {"result": "pr_open", "pr": created.get("url"), "sha": pushed["sha"]}
