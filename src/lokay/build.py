from __future__ import annotations

import os
from pathlib import Path

from lokay.git import push, worktree_add
from lokay.host_guard import guard, failure
from lokay.gh import pr_create
from lokay.run import run_process
from lokay.safety import untrusted_issue_block

DROP = ("GH_TOKEN", "GITHUB_TOKEN")


def child_env(base: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in base.items() if key not in DROP}


def _git(repo: Path, args: list[str]) -> str:
    proc = run_process(["git", *args], cwd=repo, timeout=30)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "").strip())
    return (proc.stdout or "").strip()


def build_code(
    worktree: Path,
    plan: str,
    title: str,
    body: str | None,
    env: dict[str, str],
    expected_branch: str | None = None,
    clone_path: Path | str | None = None,
) -> dict:
    clean = child_env(env)
    prompt = (
        Path(__file__).resolve().parents[2].joinpath("prompts/build.md").read_text()
        + "\n\nPlan:\n" + plan
        + "\n\n" + untrusted_issue_block(title, body)
    )
    changes = {"changed": False}
    try:
        with guard([Path(__file__).resolve().parents[2], clone_path]) as changes:
            proc = run_process(
                ["pi", "-p", "--provider", clean.get("LOKAY2_PROVIDER", ""), "--model", clean.get("LOKAY2_MODEL", ""), prompt],
                cwd=worktree,
                env=clean,
                timeout=3600,
            )
    except Exception:
        if changes["changed"]:
            return failure(changes, worktree)
        raise
    if changes["changed"]:
        return failure(changes, worktree)
    if proc.returncode != 0:
        explanation = ((proc.stderr or proc.stdout or "").strip() or "pi exited non-zero")[-500:]
        return {"result": "failed", "reason": "pi_exit", "explanation": explanation, "artifact": explanation}
    from lokay.scope import is_test

    added = set()
    for args in (["diff", "--name-status", "--diff-filter=A", "origin/main..HEAD"],
                 ["diff", "--name-status", "--diff-filter=A", "HEAD"],
                 ["diff", "--cached", "--name-status", "--diff-filter=A"]):
        added.update(line.split("\t", 1)[1] for line in _git(worktree, args).splitlines() if "\t" in line)
    added.update(_git(worktree, ["ls-files", "--others", "--exclude-standard"]).splitlines())
    removed = sorted(path for path in added if is_test(path))
    for path in removed:
        _git(worktree, ["rm", "-f", "--ignore-unmatch", "--", path])
        file = worktree / path
        if file.exists() or file.is_symlink():
            file.unlink()
    status = _git(worktree, ["status", "--porcelain"])
    if status:
        _git(worktree, ["add", "-A"])
        _git(worktree, ["reset", "-q", "--", "__pycache__"])
        _git(worktree, ["commit", "-m", "lokay build"])
    if removed:
        remaining = _git(worktree, ["diff", "--name-only", "origin/main", "HEAD"]).splitlines()
        if not any(not is_test(path) for path in remaining):
            return {"result": "failed", "reason": "tests_only",
                    "explanation": "Build added only tests: " + ", ".join(removed) + ". Implement the production change."}
    branch_now = _git(worktree, ["rev-parse", "--abbrev-ref", "HEAD"])
    log = _git(worktree, ["log", "--oneline", "origin/main..HEAD"])
    head = _git(worktree, ["rev-parse", "HEAD"])
    wrong = expected_branch is not None and branch_now != expected_branch
    pi_tail = (proc.stdout or proc.stderr or "")[-1500:]
    if wrong:
        where = expected_branch or "lokay/<issue>"
        explanation = (
            f"commit is outside the issue worktree {worktree}: "
            f"HEAD {head} on {branch_now}, expected branch {where}. pi said:\n" + pi_tail
        )
        return {
            "result": "failed",
            "reason": "outside_worktree",
            "explanation": explanation,
            "artifact": str(worktree),
        }
    if not log:
        return {
            "result": "failed",
            "reason": "no_changes",
            "explanation": f"pi exited 0 but made no commits in {worktree}. pi said:\n" + pi_tail,
            "artifact": str(worktree),
        }
    return {"result": "done", "artifact": head}


def build_publish(worktree: Path, branch: str, expected: str | None, repo_name: str, issue: int, title: str, plan_path: Path) -> dict:
    try:
        body = plan_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError(f"cannot read plan {plan_path}: {exc}") from exc
    pushed = push(worktree, branch, expected)
    if pushed["result"] != "pushed":
        return {"result": pushed["result"], "pr": None, "sha": pushed.get("sha", "")}
    created = pr_create(repo_name, branch, title, body, issue)
    return {"result": "pr_open", "pr": created.get("url"), "sha": pushed["sha"]}
