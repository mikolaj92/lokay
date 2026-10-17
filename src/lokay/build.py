from __future__ import annotations

import os
import re
import hashlib
from contextlib import contextmanager
from pathlib import Path
from typing import cast

from lokay import store

from lokay.effects.git import base_branch, git_try, commit_paths, git, head as git_head, push
from lokay.effects.gh import checks_table, open_pr_for, pr_create
from lokay.effects.pi import pi_env, run_pi
from lokay.effects.tests import check_uv_lock
from lokay.safety import untrusted_issue_block
from lokay.scope import CACHE_PATTERNS, is_artifact, is_cache
from lokay.types import IssueKind

LOCKFILES = {"uv.lock": "pyproject.toml", "poetry.lock": "pyproject.toml",
             "package-lock.json": "package.json", "pnpm-lock.yaml": "package.json",
             "yarn.lock": "package.json", "pixi.lock": "pixi.toml",
             "Cargo.lock": "Cargo.toml", "Gemfile.lock": "Gemfile",
             "composer.lock": "composer.json", "bun.lockb": "package.json"}


def exclude_caches(worktree: Path) -> None:
    exclude = worktree / git(worktree, "rev-parse", "--git-path", "info/exclude")
    existing = exclude.read_text() if exclude.exists() else ""
    missing = [pattern for pattern in CACHE_PATTERNS if pattern not in existing.splitlines()]
    if missing:
        store.append_text(exclude, ("\n" if existing and not existing.endswith("\n") else "")
                          + "\n".join(missing) + "\n")


def worktree_status(worktree: Path) -> dict[str, tuple[str, str]]:
    code, out, err = git_try(worktree, "status", "--porcelain", "-z", "--untracked-files=all", timeout=30)
    if code:
        raise RuntimeError((err or out).strip())
    entries = iter(out.split("\0"))
    names = set()
    for entry in entries:
        if not entry:
            continue
        names.add(entry[3:])
        if "R" in entry[:2] or "C" in entry[:2]:
            names.add(next(entries))
    result = {}
    for name in names:
        file = worktree / name
        content = (os.readlink(file).encode() if file.is_symlink() else
                   file.read_bytes() if file.is_file() else b"")
        result[name] = (hashlib.sha256(content).hexdigest(),
                        git(worktree, "diff", "--cached", "--binary", "--", name))
    return result


@contextmanager
def generated_cleanup(worktree: Path):
    drifted = []
    if not (worktree / ".git").exists():
        yield drifted
        return
    before = set(filter(None, git(worktree, "ls-files", "--others", "--exclude-standard", "-z").split("\0")))
    locks = {name: (worktree / name).read_bytes() if (worktree / name).is_file() else None
             for name in git(worktree, "ls-files", "-z").split("\0")
             if Path(name).name in LOCKFILES}
    try:
        yield drifted
    finally:
        drifted.extend(name for name, content in sorted(locks.items())
                       if ((worktree / name).read_bytes() if (worktree / name).is_file() else None) != content)
        after = set(filter(None, git(worktree, "ls-files", "--others", "--exclude-standard", "-z").split("\0")))
        generated = {name for name in after - before if Path(name).name not in LOCKFILES}
        if generated:
            git(worktree, "--literal-pathspecs", "clean", "-fd", "--", *sorted(generated))


def tidy_and_commit(worktree: Path, message: str, before: dict | None = None) -> tuple[list[str], list[str]]:
    merge_head = worktree / git(worktree, "rev-parse", "--git-path", "MERGE_HEAD")
    if merge_head.exists():
        if git(worktree, "ls-files", "-u"):
            git(worktree, "merge", "--abort")
        else:
            git(worktree, "commit", "--no-edit")

    def names(args: list[str]) -> set[str]:
        return set(filter(None, git(worktree, *args).split("\0")))

    base = f"origin/{base_branch(worktree)}"
    modified = names(["diff", "--name-only", "-z", "HEAD"])
    manifests = (modified | names(["diff", "--name-only", "-z", f"{base}..HEAD"])
                 | names(["ls-files", "--others", "--exclude-standard", "-z"]))
    siblings = LOCKFILES
    branch_changes = names(["diff", "--name-only", "-z", f"{base}...HEAD"])
    valid_locks = {path for path in sorted(modified | branch_changes)
                   if Path(path).name == "uv.lock"
                   and str(Path(path).with_name("pyproject.toml")) not in manifests
                   and (worktree / path).is_file()
                   and (worktree / path).with_name("pyproject.toml").is_file()
                   and check_uv_lock((worktree / path).parent)[0] == "pass"}
    stale_locks = sorted(path for path in branch_changes - valid_locks if Path(path).name in siblings
                         and str(Path(path).with_name(siblings[Path(path).name])) not in manifests)
    for path in stale_locks:
        if path in names(["ls-tree", "-r", "--name-only", "-z", base]):
            git(worktree, "checkout", base, "--", path)
        else:
            git(worktree, "rm", "-f", "--ignore-unmatch", "--", path)
    junk = sorted(path for path in modified - valid_locks if path not in stale_locks and Path(path).name in siblings
                  and str(Path(path).with_name(siblings[Path(path).name])) not in manifests)
    tracked = names(["ls-tree", "-r", "--name-only", "-z", "HEAD"])
    cache_paths = {path for path in modified | branch_changes if is_cache(path)}
    if cache_paths:
        git(worktree, "--literal-pathspecs", "rm", "-r", "-f", "--ignore-unmatch", "--", *sorted(cache_paths))
    artifacts = {path for path in modified if is_artifact(path, worktree)
                 and (path not in tracked or is_cache(path) or path.startswith("tmp/"))}
    junk = sorted(set(junk) | artifacts)
    restore = sorted((set(junk) & tracked) - cache_paths)
    if restore:
        git(worktree, "checkout", "HEAD", "--", *restore)
    added = sorted(artifacts - tracked)
    if added:
        git(worktree, "rm", "-r", "--cached", "-f", "--ignore-unmatch", "--", *added)
    untracked = names(["ls-files", "--others", "--exclude-standard", "-z"])
    untracked |= names(["ls-files", "--others", "--ignored", "--exclude-standard", "-z"])
    directories = set()
    for name in sorted(untracked):
        path = Path(name)
        if not is_artifact(name, worktree):
            continue
        file = worktree / path
        if file.is_symlink() or file.is_file():
            store.remove_file(file)
        elif file.is_dir() and not any(item.startswith(path.as_posix().rstrip("/") + "/") for item in tracked):
            store.remove_directory(file)
        for parent in path.parents:
            if is_cache(parent.as_posix()):
                directories.add(worktree / parent)
    for root, dirs, _ in os.walk(worktree, followlinks=False):
        dirs[:] = [name for name in dirs if name != ".git"]
        relative = Path(root).relative_to(worktree)
        if is_cache(relative.as_posix()):
            directories.add(Path(root))
    for directory in sorted(directories, key=lambda p: (-len(p.parts), str(p))):
        try:
            directory.rmdir()
        except OSError:
            pass
    exclude_caches(worktree)
    after = worktree_status(worktree)
    selected = sorted(path for path in after if path != ".lokay" and not path.startswith(".lokay/")
                      and (path in cache_paths or path in stale_locks or path in valid_locks
                           or before is None or before.get(path) != after[path]))
    index_paths = names(["ls-files", "-z"])
    stage = [path for path in selected
             if not path.endswith("/") and not (worktree / path).is_dir()
             and (not is_artifact(path, worktree)
                 or (path in index_paths and not (worktree / path).exists()
                     and not (worktree / path).is_symlink()))
             and (path in index_paths or (worktree / path).exists()
                  or (worktree / path).is_symlink())]
    committed = commit_paths(worktree, stage, message)
    return committed, junk


def pr_body(worktree: Path, plan_path: Path, issue: int, verdict: dict | None = None) -> str:
    try:
        plan = plan_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError(f"cannot read plan {plan_path}: {exc}") from exc
    goal = re.search(r"^## Cel[^\n]*\n.*?(?=^## |\Z)", plan, re.MULTILINE | re.DOTALL)
    base = f"origin/{base_branch(worktree)}"
    stat = git(worktree, "diff", "--stat", f"{base}...HEAD")
    body = f"Issue #{issue}\n\n" + (goal.group().strip() if goal else "## Cel")
    body += f"\n\n## Zmienione pliki\n\n```text\n{stat}\n```\n"
    if verdict and verdict.get("checks"):
        body += f"\n## Checks\n\nSHA: `{verdict.get('sha', '')}`\n\n" + checks_table(verdict["checks"])
    return body


def recover_no_changes(worktree: Path, outcome: dict, branch: str | None, *, picked: dict | None = None) -> dict:
    if picked is None:
        upstream = (git(worktree, "for-each-ref", "--format=%(upstream:short)", f"refs/heads/{branch}") if branch else "")
        if branch is not None and upstream == f"origin/{branch}":
            git(worktree, "fetch", "origin", branch)
            if int(git(worktree, "rev-list", "--count", f"{upstream}..HEAD")) > 0:
                return {"result": "done", "artifact": outcome["head"], "pi_response": outcome["pi_tail"]}
        return {
            "result": "failed",
            "reason": "no_changes",
            "explanation": f"pi exited 0 but made no commits in {worktree}. pi said:\n" + outcome["pi_tail"],
            "artifact": str(worktree),
        }
    if outcome.get("result") == "no_changes" or outcome.get("reason") == "no_changes":
        pr = open_pr_for(picked["repo"], cast(str, branch))
        if pr:
            base = base_branch(worktree)
            git(worktree, "fetch", "origin", base)
            if int(git(worktree, "rev-list", "--count", f"origin/{base}..HEAD")) > 0:
                store.rounds_append(picked["repo"], picked["issue"],
                                   "no_changes: fix already on branch, checking existing PR")
                outcome = {**outcome, "result": "done", "reason": None,
                           "artifact": git_head(worktree)}
        if outcome.get("result") == "no_changes":
            outcome = {**outcome, "result": "failed", "reason": "no_changes"}
    return outcome


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
    kind: IssueKind = "code",
) -> dict:
    previous_head = previous_head or git_head(worktree)
    clean = pi_env(env, worktree)
    clean["UV_PROJECT_ENVIRONMENT"] = str(worktree.resolve() / ".venv")
    exclude_caches(worktree)
    before = worktree_status(worktree)
    prompt = (
        Path(__file__).resolve().parents[2].joinpath("prompts/build.md").read_text()
        + "\n\nPlan:\n" + plan
        + "\n\n" + untrusted_issue_block(title, body)
        + ("\n\n" + build_note if build_note else "")
    )
    if kind == "docs_change":
        prompt += "\n\n" + Path(__file__).resolve().parents[2].joinpath("prompts/build_docs_change.md").read_text()
    proc = run_pi(
        worktree,
        prompt,
        clone_path,
        env=clean,
        cwd=worktree,
        timeout=3600,
    )
    if isinstance(proc, dict):
        return proc
    if proc.returncode != 0:
        tidy_and_commit(worktree, "lokay build", before)
        explanation = ((proc.stderr or proc.stdout or "").strip() or "pi exited non-zero")[-500:]
        return {"result": "failed", "reason": "pi_exit", "explanation": explanation, "artifact": explanation}
    from lokay.scope import is_test

    base = f"origin/{base_branch(worktree)}"
    added = set()
    for args in (["diff", "--name-status", "--diff-filter=A", f"{base}..HEAD"],
                 ["diff", "--name-status", "--diff-filter=A", "HEAD"],
                 ["diff", "--cached", "--name-status", "--diff-filter=A"]):
        added.update(line.split("\t", 1)[1] for line in git(worktree, *args).splitlines() if "\t" in line)
    added.update(git(worktree, "ls-files", "--others", "--exclude-standard").splitlines())
    removed = sorted(path for path in added if is_test(path))
    for path in removed:
        git(worktree, "rm", "-f", "--ignore-unmatch", "--", path)
        file = worktree / path
        if file.exists() or file.is_symlink():
            store.remove_file(file)
    tidy_and_commit(worktree, "lokay build", before)
    if removed:
        remaining = git(worktree, "diff", "--name-only", base, "HEAD").splitlines()
        deleted = set(git(worktree, "diff", "--name-only", "--diff-filter=D", previous_head, "HEAD").splitlines())
        if not any(not is_test(path) for path in remaining) and not (deleted & set(removed)):
            return {"result": "failed", "reason": "tests_only",
                    "explanation": "Build added only tests: " + ", ".join(removed) + ". Implement the production change."}
    branch_now = git(worktree, "rev-parse", "--abbrev-ref", "HEAD")
    log = git(worktree, "log", "--oneline", f"{previous_head}..HEAD")
    head = git_head(worktree)
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
        return recover_no_changes(worktree, {"head": head, "pi_tail": pi_tail}, expected_branch)
    return {"result": "done", "artifact": head, "pi_response": pi_tail}


def fix_code(worktree: Path, previous: str, prompt: str, env: dict[str, str], clone_path: Path | str | None = None) -> dict:
    before = worktree_status(worktree)
    clean = pi_env(env, worktree)
    clean["UV_PROJECT_ENVIRONMENT"] = str(worktree.resolve() / ".venv")
    proc = run_pi(
        worktree,
        prompt,
        clone_path,
        env=clean,
        cwd=worktree,
        timeout=3600,
        missing_is_failure=True,
    )
    if isinstance(proc, dict):
        return proc
    tidy_and_commit(worktree, "lokay fix", before)
    if proc.returncode != 0:
        return {"result": "failed", "artifact": ""}
    code, out, err = git_try(worktree, "rev-parse", "HEAD", timeout=30)
    if code:
        raise RuntimeError(err.strip())
    sha = out.strip()
    if sha == previous:
        return {"result": "failed", "reason": "no_changes", "artifact": "",
                "pi_response": proc.stdout or proc.stderr or ""}
    return {"result": "done", "artifact": sha, "pi_response": (proc.stdout or proc.stderr or "")[-1500:]}


def fix_publish(worktree: Path, branch: str, expected: str | None) -> dict:
    pushed = push(worktree, branch, expected)
    if pushed["result"] != "pushed":
        return {"result": pushed["result"], "sha": pushed.get("sha", "")}
    return {"result": "pushed", "sha": pushed["sha"]}


def build_publish(worktree: Path, branch: str, expected: str | None, repo_name: str, issue: int, title: str, plan_path: Path) -> dict:
    from lokay.store import state_read

    saved = state_read(repo_name, issue)
    body = pr_body(worktree, plan_path, issue, saved.get("last_check") or saved.get("verdict"))
    pushed = push(worktree, branch, expected)
    if pushed["result"] != "pushed":
        return {"result": pushed["result"], "pr": None, "sha": pushed.get("sha", "")}
    created = pr_create(repo_name, branch, title, body, issue)
    return {"result": "pr_open", "pr": created.get("url"), "sha": pushed["sha"]}
