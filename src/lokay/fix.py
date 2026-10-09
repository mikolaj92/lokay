from __future__ import annotations

from pathlib import Path

from lokay.build import child_env
from lokay.git import push
from lokay.run import run_process


def _git(repo: Path, args: list[str]) -> str:
    proc = run_process(["git", *args], cwd=repo, timeout=30)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "").strip())
    return (proc.stdout or "").strip()


def fix_code(worktree: Path, previous: str, prompt: str, env: dict[str, str]) -> dict:
    try:
        proc = run_process(
            ["pi", "-p", "--provider", env.get("LOKAY2_PROVIDER", ""), "--model", env.get("LOKAY2_MODEL", ""), prompt],
            cwd=worktree,
            env=child_env(env),
            timeout=3600,
        )
    except FileNotFoundError:
        return {"result": "failed", "artifact": ""}
    if proc.returncode != 0:
        return {"result": "failed", "artifact": ""}
    status = _git(worktree, ["status", "--porcelain"])
    if status:
        _git(worktree, ["add", "-A"])
        _git(worktree, ["commit", "-m", "lokay fix"])
    sha = _git(worktree, ["rev-parse", "HEAD"])
    if sha == previous:
        return {"result": "failed", "artifact": ""}
    return {"result": "done", "artifact": sha}


def fix_publish(worktree: Path, branch: str, expected: str | None) -> dict:
    pushed = push(worktree, branch, expected)
    if pushed["result"] != "pushed":
        return {"result": pushed["result"], "sha": pushed.get("sha", "")}
    return {"result": "pushed", "sha": pushed["sha"]}
