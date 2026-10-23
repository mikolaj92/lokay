from __future__ import annotations

import os
import hashlib
from contextlib import contextmanager
from pathlib import Path

from lokay import store

from lokay.effects.git import base_branch, git_try, commit_paths, git, git_bytes, push
from lokay.effects.gh import checks_table, pr_create
from lokay.effects.tests import check_uv_lock
from lokay.scope import CACHE_PATTERNS, is_artifact, is_cache, is_junk

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


def worktree_status(worktree: Path, paths: set[str] | None = None) -> dict[str, tuple[str, bytes]]:
    if paths == set():
        return {}
    code, out, err = git_try(worktree, "--literal-pathspecs", "status", "--porcelain", "-z",
                             "--untracked-files=all", *(["--", *sorted(paths)] if paths is not None else []),
                             timeout=30)
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
                        git_bytes(worktree, "diff", "--cached", "--binary", "--", name))
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


def tidy_and_commit(worktree: Path, message: str, before: dict | None = None,
                    paths: set[str] | None = None) -> tuple[list[str], list[str]]:
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
    cache_paths = {path for path in modified | branch_changes if is_cache(path) or is_junk(path, worktree)}
    candidates = branch_changes - names(["ls-tree", "-r", "--name-only", "-z", base])
    if candidates:
        code, out, err = git_try(worktree, "check-ignore", "--no-index", "--stdin", "-z",
                                 input="\0".join(sorted(candidates)) + "\0")
        if code not in (0, 1):
            raise RuntimeError((err or out).strip())
        cache_paths.update(filter(None, out.split("\0")))
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
    if paths is not None:
        untracked &= paths
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
    for root, dirs, _ in (os.walk(worktree, followlinks=False) if paths is None else ()):
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
    after = worktree_status(worktree, paths | cache_paths | set(stale_locks) | valid_locks
                            if paths is not None else None)
    selected = sorted(path for path in after if path != ".lokay" and not path.startswith(".lokay/")
                      and (path in cache_paths or path in stale_locks or path in valid_locks
                           or before is None or before.get(path) != after[path]))
    index_paths = names(["ls-files", "-z"])
    stage = [path for path in selected
             if not path.endswith("/") and not (worktree / path).is_dir()
             and (not is_artifact(path, worktree) or path in tracked
                 or (path in index_paths and not (worktree / path).exists()
                     and not (worktree / path).is_symlink()))
             and (path in tracked or path in index_paths or (worktree / path).exists()
                  or (worktree / path).is_symlink())]
    committed = commit_paths(worktree, stage, message)
    return committed, junk


def pr_body(worktree: Path, spec: str, issue: int, verdict: dict | None = None) -> str:
    base = f"origin/{base_branch(worktree)}"
    stat = git(worktree, "diff", "--stat", f"{base}...HEAD")
    body = f"Issue #{issue}\n\n" + spec
    body += f"\n\n## Zmienione pliki\n\n```text\n{stat}\n```\n"
    if verdict and verdict.get("checks"):
        body += f"\n## Checks\n\nSHA: `{verdict.get('sha', '')}`\n\n" + checks_table(verdict["checks"])
    return body


def build_publish(worktree: Path, branch: str, expected: str | None, repo_name: str, issue: int, title: str, spec: str) -> dict:
    from lokay.store import state_read
    from lokay.types import pr_number

    saved = state_read(repo_name, issue)
    body = pr_body(worktree, spec, issue, saved.get("last_check") or saved.get("verdict"))
    pushed = push(worktree, branch, expected)
    if pushed["result"] != "pushed":
        return {"result": pushed["result"], "pr": None, "sha": pushed.get("sha", "")}
    created = pr_create(repo_name, branch, title, body, issue)
    return {"result": "pr_open", "pr": pr_number(created.get("url")), "sha": pushed["sha"]}
