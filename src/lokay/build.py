from __future__ import annotations

import os
import re
from pathlib import Path

from lokay.git import push, worktree_add
from lokay.host_guard import guard, failure
from lokay.gh import pr_create
from lokay.run import run_process
from lokay.safety import untrusted_issue_block
from lokay.scope import is_artifact

DROP = ("GH_TOKEN", "GITHUB_TOKEN")


def child_env(base: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in base.items() if key not in DROP}


def _git(repo: Path, args: list[str]) -> str:
    proc = run_process(["git", *args], cwd=repo, timeout=30)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "").strip())
    return (proc.stdout or "").strip()


def tidy_and_commit(worktree: Path, message: str) -> tuple[list[str], list[str]]:
    """Restore incidental edits, remove untracked artifacts, commit the rest."""
    def names(args: list[str]) -> set[str]:
        return set(filter(None, _git(worktree, args).split("\0")))

    modified = names(["diff", "--name-only", "-z", "HEAD"])
    manifests = (modified | names(["diff", "--name-only", "-z", "origin/main..HEAD"])
                 | names(["ls-files", "--others", "--exclude-standard", "-z"]))
    siblings = {"uv.lock": "pyproject.toml", "poetry.lock": "pyproject.toml",
                "package-lock.json": "package.json"}
    junk = sorted(path for path in modified if Path(path).name in siblings
                  and str(Path(path).with_name(siblings[Path(path).name])) not in manifests)
    tracked = names(["ls-tree", "-r", "--name-only", "-z", "HEAD"])
    artifacts = {path for path in modified if is_artifact(path)
                 and (path not in tracked or path.startswith((".check-local/", "tmp/")))}
    junk = sorted(set(junk) | artifacts)
    restore = sorted(set(junk) & tracked)
    if restore:
        _git(worktree, ["checkout", "HEAD", "--", *restore])
    added = sorted(artifacts - tracked)
    if added:
        _git(worktree, ["rm", "-r", "--cached", "-f", "--ignore-unmatch", "--", *added])
    caches = {"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".venv", ".check-local"}
    untracked = names(["ls-files", "--others", "--exclude-standard", "-z"])
    untracked |= names(["ls-files", "--others", "--ignored", "--exclude-standard", "-z"])
    directories = set()
    for name in sorted(untracked):
        path = Path(name)
        if not (set(path.parts) & caches or path.name.endswith(".pyc") or is_artifact(name)):
            continue
        file = worktree / path
        if file.is_file() or file.is_symlink():
            file.unlink()
        for parent in path.parents:
            if set(parent.parts) & caches:
                directories.add(worktree / parent)
    # ls-files omits empty directories. Include them without following symlinks.
    for root, dirs, _ in os.walk(worktree, followlinks=False):
        dirs[:] = [name for name in dirs if name != ".git"]
        relative = Path(root).relative_to(worktree)
        if set(relative.parts) & caches:
            directories.add(Path(root))
    for directory in sorted(directories, key=lambda p: (-len(p.parts), str(p))):
        try:
            directory.rmdir()
        except OSError:
            pass  # Keep directories containing tracked files.
    _git(worktree, ["add", "-A"])
    committed = sorted(names(["diff", "--cached", "--name-only", "-z"]))
    if committed:
        _git(worktree, ["commit", "-m", message])
    return committed, junk


def pr_body(worktree: Path, plan_path: Path) -> str:
    try:
        plan = plan_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError(f"cannot read plan {plan_path}: {exc}") from exc
    goal = re.search(r"^## Cel[^\n]*\n.*?(?=^## |\Z)", plan, re.MULTILINE | re.DOTALL)
    stat = _git(worktree, ["diff", "--stat", "origin/main...HEAD"])
    subjects = _git(worktree, ["log", "--format=%s", "origin/main..HEAD"])
    commits = "\n".join(f"- {subject}" for subject in subjects.splitlines())
    return f"## Zmiany\n\n```text\n{stat}\n```\n\n{commits}\n\n## Plan\n\n" + (goal.group().strip() if goal else "") + "\n"


def build_code(
    worktree: Path,
    plan: str,
    title: str,
    body: str | None,
    env: dict[str, str],
    expected_branch: str | None = None,
    clone_path: Path | str | None = None,
    build_note: str | None = None,
    previous_head: str | None = None,
) -> dict:
    previous_head = previous_head or _git(worktree, ["rev-parse", "HEAD"])
    clean = child_env(env)
    prompt = (
        Path(__file__).resolve().parents[2].joinpath("prompts/build.md").read_text()
        + "\n\nPlan:\n" + plan
        + "\n\n" + untrusted_issue_block(title, body)
        + ("\n\n" + build_note if build_note else "")
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
        tidy_and_commit(worktree, "lokay build")
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
    tidy_and_commit(worktree, "lokay build")
    if removed:
        remaining = _git(worktree, ["diff", "--name-only", "origin/main", "HEAD"]).splitlines()
        deleted = set(_git(worktree, ["diff", "--name-only", "--diff-filter=D", previous_head, "HEAD"]).splitlines())
        if not any(not is_test(path) for path in remaining) and not (deleted & set(removed)):
            return {"result": "failed", "reason": "tests_only",
                    "explanation": "Build added only tests: " + ", ".join(removed) + ". Implement the production change."}
    branch_now = _git(worktree, ["rev-parse", "--abbrev-ref", "HEAD"])
    log = _git(worktree, ["log", "--oneline", f"{previous_head}..HEAD"])
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
    body = pr_body(worktree, plan_path)
    pushed = push(worktree, branch, expected)
    if pushed["result"] != "pushed":
        return {"result": pushed["result"], "pr": None, "sha": pushed.get("sha", "")}
    created = pr_create(repo_name, branch, title, body, issue)
    return {"result": "pr_open", "pr": created.get("url"), "sha": pushed["sha"]}
