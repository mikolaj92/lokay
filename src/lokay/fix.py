from __future__ import annotations

from pathlib import Path

from lokay.build import tidy_and_commit, worktree_status
from lokay.git import push
from lokay.host_guard import guard, failure
from lokay.run import pi_env, run_process, sandboxed


def _git(repo: Path, args: list[str]) -> str:
    proc = run_process(["git", *args], cwd=repo, timeout=30)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "").strip())
    return (proc.stdout or "").strip()


def fix_code(worktree: Path, previous: str, prompt: str, env: dict[str, str], clone_path: Path | str | None = None) -> dict:
    before = worktree_status(worktree)
    clean = pi_env(env, worktree)
    clean["UV_PROJECT_ENVIRONMENT"] = str(worktree.resolve() / ".venv")
    changes = {"changed": False}
    try:
        with guard([Path(__file__).resolve().parents[2], clone_path]) as changes:
            proc = run_process(
                sandboxed(["pi", "-p", "--provider", env.get("LOKAY2_PROVIDER", ""), "--model", env.get("LOKAY2_MODEL", ""), prompt], worktree, clean),
                cwd=worktree,
                env=clean,
                timeout=3600,
            )
    except Exception as exc:
        if changes["changed"]:
            return failure(changes, worktree)
        if isinstance(exc, FileNotFoundError):
            return {"result": "failed", "artifact": ""}
        raise
    if changes["changed"]:
        return failure(changes, worktree)
    tidy_and_commit(worktree, "lokay fix", before)
    if proc.returncode != 0:
        return {"result": "failed", "artifact": ""}
    sha = _git(worktree, ["rev-parse", "HEAD"])
    if sha == previous:
        return {"result": "failed", "reason": "no_changes", "artifact": "",
                "pi_response": proc.stdout or proc.stderr or ""}
    return {"result": "done", "artifact": sha, "pi_response": (proc.stdout or proc.stderr or "")[-1500:]}


def fix_publish(worktree: Path, branch: str, expected: str | None) -> dict:
    pushed = push(worktree, branch, expected)
    if pushed["result"] != "pushed":
        return {"result": pushed["result"], "sha": pushed.get("sha", "")}
    return {"result": "pushed", "sha": pushed["sha"]}
