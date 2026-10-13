from __future__ import annotations

import os
import re
import hashlib
from contextlib import contextmanager
from pathlib import Path

from lokay.git import push, worktree_add
from lokay.host_guard import guard, failure
from lokay.gh import pr_create
from lokay.run import run_process
from lokay.safety import untrusted_issue_block
from lokay.scope import CACHE_PATTERNS, is_artifact, is_cache

DROP = ("GH_TOKEN", "GITHUB_TOKEN")


def child_env(base: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in base.items() if key not in DROP}


def _git(repo: Path, args: list[str]) -> str:
    proc = run_process(["git", *args], cwd=repo, timeout=30)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "").strip())
    return (proc.stdout or "").strip()


def exclude_caches(worktree: Path) -> None:
    exclude = worktree / _git(worktree, ["rev-parse", "--git-path", "info/exclude"])
    existing = exclude.read_text() if exclude.exists() else ""
    missing = [pattern for pattern in CACHE_PATTERNS if pattern not in existing.splitlines()]
    if missing:
        exclude.parent.mkdir(parents=True, exist_ok=True)
        with exclude.open("a") as file:
            file.write(("\n" if existing and not existing.endswith("\n") else "")
                       + "\n".join(missing) + "\n")


def worktree_status(worktree: Path) -> dict[str, tuple[str, str]]:
    """Snapshot dirty paths, including edits with unchanged status codes."""
    _git(worktree, ["status", "--porcelain", "-z", "--untracked-files=all"])
    names = set()
    for args in (["ls-files", "-m", "-d", "--others", "--exclude-standard", "-z"],
                 ["diff", "--cached", "--name-only", "-z"]):
        names.update(filter(None, _git(worktree, args).split("\0")))
    result = {}
    for name in names:
        file = worktree / name
        content = (os.readlink(file).encode() if file.is_symlink() else
                   file.read_bytes() if file.is_file() else b"")
        result[name] = (hashlib.sha256(content).hexdigest(),
                        _git(worktree, ["diff", "--cached", "--binary", "--", name]))
    return result


@contextmanager
def generated_cleanup(worktree: Path):
    """Keep ignored environments; discard setup/CI output and lock rewrites."""
    from lokay.merge_guard import LOCKFILES

    if not (worktree / ".git").exists():
        yield
        return
    before = set(filter(None, _git(worktree, ["ls-files", "--others", "--exclude-standard", "-z"]).split("\0")))
    locks = [name for name in _git(worktree, ["ls-files", "-z"]).split("\0")
             if Path(name).name in LOCKFILES]
    try:
        yield
    finally:
        if locks:
            _git(worktree, ["checkout", "HEAD", "--", *locks])
        after = set(filter(None, _git(worktree, ["ls-files", "--others", "--exclude-standard", "-z"]).split("\0")))
        if after - before:
            _git(worktree, ["--literal-pathspecs", "clean", "-fd", "--", *sorted(after - before)])


def tidy_and_commit(worktree: Path, message: str, before: dict | None = None) -> tuple[list[str], list[str]]:
    """Restore incidental edits, remove untracked artifacts, commit pi's paths."""
    def names(args: list[str]) -> set[str]:
        return set(filter(None, _git(worktree, args).split("\0")))

    modified = names(["diff", "--name-only", "-z", "HEAD"])
    manifests = (modified | names(["diff", "--name-only", "-z", "origin/main..HEAD"])
                 | names(["ls-files", "--others", "--exclude-standard", "-z"]))
    from lokay.merge_guard import LOCKFILES

    siblings = LOCKFILES
    branch_changes = names(["diff", "--name-only", "-z", "origin/main...HEAD"])
    stale_locks = sorted(path for path in branch_changes if Path(path).name in siblings
                         and str(Path(path).with_name(siblings[Path(path).name])) not in manifests)
    for path in stale_locks:
        if path in names(["ls-tree", "-r", "--name-only", "-z", "origin/main"]):
            _git(worktree, ["checkout", "origin/main", "--", path])
        else:
            _git(worktree, ["rm", "-f", "--ignore-unmatch", "--", path])
    junk = sorted(path for path in modified if path not in stale_locks and Path(path).name in siblings
                  and str(Path(path).with_name(siblings[Path(path).name])) not in manifests)
    tracked = names(["ls-tree", "-r", "--name-only", "-z", "HEAD"])
    cache_paths = {path for path in modified | branch_changes if is_cache(path)}
    if cache_paths:
        _git(worktree, ["--literal-pathspecs", "rm", "-r", "-f", "--ignore-unmatch", "--", *sorted(cache_paths)])
    artifacts = {path for path in modified if is_artifact(path)
                 and (path not in tracked or is_cache(path) or path.startswith("tmp/"))}
    junk = sorted(set(junk) | artifacts)
    restore = sorted((set(junk) & tracked) - cache_paths)
    if restore:
        _git(worktree, ["checkout", "HEAD", "--", *restore])
    added = sorted(artifacts - tracked)
    if added:
        _git(worktree, ["rm", "-r", "--cached", "-f", "--ignore-unmatch", "--", *added])
    untracked = names(["ls-files", "--others", "--exclude-standard", "-z"])
    untracked |= names(["ls-files", "--others", "--ignored", "--exclude-standard", "-z"])
    directories = set()
    for name in sorted(untracked):
        path = Path(name)
        if not is_artifact(name):
            continue
        file = worktree / path
        if file.is_file() or file.is_symlink():
            file.unlink()
        for parent in path.parents:
            if is_cache(parent.as_posix()):
                directories.add(worktree / parent)
    # ls-files omits empty directories. Include them without following symlinks.
    for root, dirs, _ in os.walk(worktree, followlinks=False):
        dirs[:] = [name for name in dirs if name != ".git"]
        relative = Path(root).relative_to(worktree)
        if is_cache(relative.as_posix()):
            directories.add(Path(root))
    for directory in sorted(directories, key=lambda p: (-len(p.parts), str(p))):
        try:
            directory.rmdir()
        except OSError:
            pass  # Keep directories containing tracked files.
    exclude_caches(worktree)
    after = worktree_status(worktree)
    selected = sorted(path for path in after if path in cache_paths or path in stale_locks
                      or before is None or before.get(path) != after[path])
    index_paths = names(["ls-files", "-z"])
    stage = [path for path in selected if path in index_paths or (worktree / path).exists()
             or (worktree / path).is_symlink()]
    if stage:
        _git(worktree, ["--literal-pathspecs", "add", "-A", "--", *stage])
    committed = sorted(set(selected) & names(["diff", "--cached", "--name-only", "-z"]))
    if committed:
        _git(worktree, ["--literal-pathspecs", "commit", "--only", "-m", message, "--", *committed])
    return committed, junk


def pr_body(worktree: Path, plan_path: Path, pi_response: str = "") -> str:
    try:
        plan = plan_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError(f"cannot read plan {plan_path}: {exc}") from exc
    goal = re.search(r"^## Cel[^\n]*\n.*?(?=^## |\Z)", plan, re.MULTILINE | re.DOTALL)
    stat = _git(worktree, ["diff", "--stat", "origin/main...HEAD"])
    subjects = _git(worktree, ["log", "--format=%s", "origin/main..HEAD"])
    commits = "\n".join(f"- {subject}" for subject in subjects.splitlines())
    files = _git(worktree, ["diff", "--name-only", "-z", "origin/main...HEAD"])
    changed = "\n".join(f"- `{name}`" for name in files.split("\0") if name)
    done = f"## Co zrobiono\n\n{pi_response[-1500:].strip()}\n\n### Zmienione pliki\n\n{changed}\n\n"
    return done + f"## Zmiany\n\n```text\n{stat}\n```\n\n{commits}\n\n## Plan\n\n" + (goal.group().strip() if goal else "") + "\n"


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
    clean["UV_PROJECT_ENVIRONMENT"] = str(worktree.resolve() / ".venv")
    exclude_caches(worktree)
    before = worktree_status(worktree)
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
        tidy_and_commit(worktree, "lokay build", before)
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
    tidy_and_commit(worktree, "lokay build", before)
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
    return {"result": "done", "artifact": head, "pi_response": pi_tail}


def build_publish(worktree: Path, branch: str, expected: str | None, repo_name: str, issue: int, title: str, plan_path: Path) -> dict:
    from lokay.state import state_read

    body = pr_body(worktree, plan_path, state_read(repo_name, issue).get("pi_response") or "")
    pushed = push(worktree, branch, expected)
    if pushed["result"] != "pushed":
        return {"result": pushed["result"], "pr": None, "sha": pushed.get("sha", "")}
    created = pr_create(repo_name, branch, title, body, issue)
    return {"result": "pr_open", "pr": created.get("url"), "sha": pushed["sha"]}
