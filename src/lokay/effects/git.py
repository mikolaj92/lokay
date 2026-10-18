from __future__ import annotations

import os
import re
from subprocess import CompletedProcess
from typing import Any
from pathlib import Path

from lokay.effects.pi import run_process
from lokay.effects.retry import retry
from lokay.safety import validate_argv

REF_LOCK = ("cannot lock ref", "unable to resolve reference", ".lock")
BASE_BRANCHES: dict[tuple[Path, str | None], str] = {}
REPOSITORIES: dict[Path, dict] = {}


def base_branch(path: Path, *, branch: str | None = None) -> str:
    path = path.resolve()
    key = (path, branch)
    if key in BASE_BRANCHES:
        return BASE_BRANCHES[key]
    from lokay.effects.gh import _gh, open_pr_for
    import json

    def checked(args):
        code, out, err = git_try(path, *args)
        if code:
            raise RuntimeError(err or out)
        return out.strip()

    root = Path(checked(["rev-parse", "--show-toplevel"]))
    root_key = (root, branch)
    if root_key not in BASE_BRANCHES:
        common = (path / checked(["rev-parse", "--git-common-dir"])).resolve()
        if common not in REPOSITORIES:
            code, out, err = _gh(["repo", "view", "--json", "nameWithOwner,defaultBranchRef"], cwd=root)
            if code == 0:
                REPOSITORIES[common] = json.loads(out)
        repo = REPOSITORIES.get(common, {})
        head = branch if branch is not None else checked(["branch", "--show-current"])
        pr = open_pr_for(repo["nameWithOwner"], head) if head and repo else None
        base = (pr or {}).get("baseRefName") or (repo.get("defaultBranchRef") or {}).get("name")
        if not base:
            code, out, err = git_try(path, "symbolic-ref", "refs/remotes/origin/HEAD")
            base = out.strip().removeprefix("refs/remotes/origin/") if code == 0 else ""
            base = base or "main"
        if common not in REPOSITORIES:
            return base
        BASE_BRANCHES[root_key] = base
    BASE_BRANCHES[key] = BASE_BRANCHES[root_key]
    return BASE_BRANCHES[root_key]


def _command(repo: Path | None, args: list[str], *, timeout: float, env: dict[str, str] | None = None,
             input: bytes | None = None, text: bool = True) -> CompletedProcess[Any]:
    argv = ["git", *args]
    validate_argv(argv)
    return run_process(argv, cwd=repo, timeout=timeout, env=env, input=input, text=text)


def git_try(path: Path, *args: str, timeout: float = 60, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    proc = _command(path, list(args), timeout=timeout, env=env)
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def git(path: Path, *args: str, timeout: float = 30) -> str:
    code, out, err = git_try(path, *args, timeout=timeout)
    if code:
        raise RuntimeError((err or out).strip())
    return out.strip()


def head(path: Path) -> str:
    return git(path, "rev-parse", "HEAD")


def commit_time(repo: Path, ref: str) -> str:
    if not ref or ref.startswith("-") or any(char.isspace() for char in ref):
        raise ValueError("expected a git tag or sha")
    code, out, err = git_try(repo, "show", "-s", "--format=%cI", "--end-of-options", f"{ref}^{{commit}}", "--")
    if code:
        raise ValueError(err.strip() or out.strip())
    return out.strip()


def merge_conflicts(repo: Path, sha: str) -> list[str]:
    if not isinstance(sha, str) or not re.fullmatch(r"[a-fA-F0-9]{7,64}", sha):
        raise ValueError("expected a hex sha of 7-64 characters")
    try:
        base = base_branch(repo)
        code, out, _ = git_try(repo, "merge-tree", "--write-tree", "--name-only", "-z", f"origin/{base}", sha)
        if code == 0:
            return []
        if code == 1:
            fields = out.split("\0")
            end = fields.index("", 1)
            if re.fullmatch(r"(?:[a-fA-F0-9]{40}|[a-fA-F0-9]{64})", fields[0]) and end > 1:
                return fields[1:end]
    except Exception:
        raise RuntimeError("merge conflict check failed") from None
    raise RuntimeError("merge conflict check failed")


def merge_files(repo: Path, sha: str) -> list[dict] | None:
    if not isinstance(sha, str) or not re.fullmatch(r"[a-fA-F0-9]{7,64}", sha):
        raise ValueError("expected a hex sha of 7-64 characters")
    if not repo.is_dir():
        return None
    env = {**os.environ, "GIT_NO_LAZY_FETCH": "1"}
    code, out, err = git_try(repo, "show", "--first-parent", "-m", "--name-only", "--format=", "-z", sha, "--", env=env)
    if code or not out:
        code, out, err = git_try(repo, "diff-tree", "--name-only", "-r", "-z", f"{sha}^1", sha, "--", env=env)
    if code:
        exists, _, error = git_try(repo, "rev-parse", "--verify", "--quiet", f"{sha}^{{object}}", env=env)
        if exists == 1:
            return None
        raise ValueError(error.strip() if exists else err.strip() or out.strip())
    return [{"path": path} for path in dict.fromkeys(out.split("\0")) if path]


def ensure_worktree(repo: Path, branch: str, path: Path) -> dict:
    def checked(where, args):
        code, out, err = git_try(where, *args)
        if code:
            raise RuntimeError(err.strip() or out.strip() or f"git {args} failed ({code})")
        return out

    def registrations():
        records = []
        record = {}
        for field in checked(repo, ["worktree", "list", "--porcelain", "-z"]).split("\0"):
            if not field:
                if record:
                    records.append(record)
                    record = {}
            else:
                key, _, value = field.partition(" ")
                record[key] = value
        if record:
            records.append(record)
        return records

    def registration():
        records = registrations()
        matches = [row for row in records
                   if row.get("worktree") is not None and Path(row["worktree"]).resolve() == path.resolve()]
        if len(matches) != 1:
            raise ValueError("expected exactly one worktree registration")
        row = matches[0]
        if (row is records[0] or row.get("branch") != f"refs/heads/{branch}" or "bare" in row
                or "detached" in row or Path(row["worktree"]).resolve() == repo):
            raise ValueError("worktree registration or branch mismatch")
        if any(row.get("branch") == f"refs/heads/{branch}"
               and (row.get("worktree") is None or Path(row["worktree"]).resolve() != path.resolve())
               for row in records):
            raise ValueError("branch registered at another worktree")
        return row

    def verify():
        registration()
        if path.is_symlink() or not path.is_dir() or not (path / ".git").is_file() or (path / ".git").is_symlink():
            raise ValueError("expected a registered linked worktree directory")
        top = checked(path, ["rev-parse", "--show-toplevel"]).strip()
        common = checked(path, ["rev-parse", "--git-common-dir"]).strip()
        git_dir = (path / checked(path, ["rev-parse", "--git-dir"]).strip()).resolve()
        head = checked(path, ["symbolic-ref", "HEAD"]).strip()
        if (Path(top).resolve() != path or (path / common).resolve() != common_dir
                or git_dir.parent != common_dir / "worktrees" or head != f"refs/heads/{branch}"):
            raise ValueError("worktree top-level, common directory or branch mismatch")

    try:
        checked(repo, ["check-ref-format", "--branch", branch])
        match = re.fullmatch(r"lokay/([1-9][0-9]*)", branch)
        if not match:
            raise ValueError("expected lokay/<positive decimal issue>")
        repo = repo.resolve()
        path = path.parent.resolve() / path.name
        expected = repo.parent / f"{repo.name}-wt-{match[1]}"
        if path.is_symlink() or path != expected or path == repo:
            raise ValueError(f"expected non-symlink sibling worktree path {expected}")
        if Path(checked(repo, ["rev-parse", "--show-toplevel"]).strip()).resolve() != repo:
            raise ValueError("repository top-level mismatch")
        common_dir = (repo / checked(repo, ["rev-parse", "--git-common-dir"]).strip()).resolve()
        if path.exists():
            verify()
            return {"result": "added", "path": str(path), "branch": branch}
        records = registrations()
        if any(row.get("worktree") is not None and Path(row["worktree"]).resolve() == path.resolve()
               for row in records):
            row = registration()
            if "locked" in row or path.exists() or path.is_symlink():
                raise ValueError("cannot recover locked or existing worktree")
            checked(repo, ["worktree", "remove", "--force", str(path)])
        if any(row.get("branch") == f"refs/heads/{branch}" for row in registrations()):
            raise ValueError("branch already registered at another worktree")
        code, out, err = git_try(repo, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}")
        if code == 0:
            args = ["worktree", "add", str(path), branch]
        elif code == 1:
            code, out, err = git_try(repo, "ls-remote", "--exit-code", "--heads", "origin", f"refs/heads/{branch}")
            if code not in (0, 2):
                raise RuntimeError(err.strip() or out.strip() or f"ls-remote failed ({code})")
            base = branch if code == 0 else "main"
            checked(repo, ["check-ref-format", "--branch", base])
            checked(repo, ["fetch", "origin", f"refs/heads/{base}:refs/remotes/origin/{base}"])
            args = ["worktree", "add", "-b", branch, str(path), f"origin/{base}"]
        else:
            raise RuntimeError(err.strip() or out.strip() or f"show-ref failed ({code})")
        checked(repo, args)
        verify()
        return {"result": "added", "path": str(path), "branch": branch}
    except (OSError, ValueError, RuntimeError) as exc:
        return {"result": "failed", "error": str(exc)}


def worktree_remove(repo: Path, path: Path, *, safe: bool = False, branch: str | None = None) -> dict:
    if safe:
        def checked(where, args):
            code, out, err = git_try(where, *args)
            if code:
                raise RuntimeError(err.strip() or out.strip() or "cleanup lookup failed")
            return out.strip()

        try:
            match = re.fullmatch(r"lokay/([1-9][0-9]*)", branch or "")
            if not match:
                raise ValueError("expected lokay/<positive decimal issue>")
            repo = repo.resolve()
            path = path.parent.resolve() / path.name
            expected = repo.parent / f"{repo.name}-wt-{match[1]}"
            if path != expected or path.is_symlink() or path == repo:
                raise ValueError("expected non-symlink sibling worktree path")
            if not path.exists():
                return {"result": "kept", "path": str(path)}
            ref = f"refs/heads/{branch}"
            if (Path(checked(repo, ["rev-parse", "--show-toplevel"])).resolve() != repo
                    or not (path / ".git").is_file() or (path / ".git").is_symlink()
                    or Path(checked(path, ["rev-parse", "--show-toplevel"])).resolve() != path
                    or checked(path, ["symbolic-ref", "HEAD"]) != ref):
                raise ValueError("worktree top-level or branch mismatch")
            common = (repo / checked(repo, ["rev-parse", "--git-common-dir"])).resolve()
            if (path / checked(path, ["rev-parse", "--git-common-dir"])).resolve() != common:
                raise ValueError("worktree repository mismatch")
            records = checked(repo, ["worktree", "list", "--porcelain", "-z"]).split("\0\0")
            matches = [record.split("\0") for record in records
                       if f"worktree {path}" in record.split("\0")]
            if (len(matches) != 1 or f"branch {ref}" not in matches[0]
                    or any(field.startswith("locked") for field in matches[0])):
                raise ValueError("worktree registration mismatch or locked")
            if checked(path, ["status", "--porcelain", "--untracked-files=all"]):
                return {"result": "kept", "path": str(path), "reason": "dirty"}
            head = checked(repo, ["rev-parse", "--verify", ref])
            if checked(path, ["rev-parse", "HEAD"]) != head:
                raise ValueError("worktree HEAD mismatch")
            reachable = checked(repo, ["for-each-ref", f"--contains={head}",
                                       "--format=%(refname)", "refs/remotes/origin/"])
            checked(repo, ["worktree", "remove", str(path)])
            if reachable:
                checked(repo, ["update-ref", "-d", ref, head])
            return {"result": "removed", "path": str(path)}
        except (OSError, ValueError, RuntimeError) as exc:
            return {"result": "failed", "error": str(exc)}
    code, out, err = git_try(repo, "worktree", "remove", "--force", str(path))
    if code != 0 and path.exists():
        return {"result": "failed", "error": err.strip() or out.strip()}
    return {"result": "removed", "path": str(path)}


def remote_sha(repo: Path, branch: str) -> str | None:
    code, out, err = git_try(repo, "ls-remote", "origin", f"refs/heads/{branch}")
    if code != 0:
        return None
    line = out.strip().splitlines()
    if not line or not line[0].strip():
        return None
    return line[0].split()[0]


def push(repo: Path, branch: str, expected_remote_sha: str | None, attempts: int = 3) -> dict:
    if branch.startswith("+") or ":" in branch:
        return {
            "result": "failed",
            "error": f"refspec {branch} is forbidden; pass a branch name",
        }
    short = branch[len("refs/heads/"):] if branch.lower().startswith("refs/heads/") else branch
    if short.lower() in {"main", "master"}:
        return {
            "result": "failed",
            "error": f"push to protected branch {branch} is forbidden; open a PR from a branch",
        }
    branch = short
    current = remote_sha(repo, branch)
    head_code, head_sha, _ = git_try(repo, "rev-parse", "HEAD")
    if (
        expected_remote_sha
        and head_code == 0
        and current == head_sha.strip()
        and current == expected_remote_sha
    ):
        return {"result": "pushed", "sha": current, "attempts": 0}
    if current != expected_remote_sha:
        return {"result": "remote_moved", "sha": current or ""}
    if attempts <= 0:
        return {"result": "failed", "error": ""}
    attempt = 0

    def push_once():
        nonlocal attempt
        attempt += 1
        code, out, err = git_try(repo, "push", "-u", "origin", branch, timeout=120)
        if code == 0:
            head, sha, _ = git_try(repo, "rev-parse", "HEAD")
            return {"result": "pushed", "sha": sha.strip(), "attempts": attempt} if head == 0 else {"result": "failed"}
        return {"result": "failed", "error": (err or out).strip()}

    def transient(result):
        if isinstance(result, Exception):
            return None
        error = result.get("error", "").lower()
        return error if any(mark in error for mark in REF_LOCK) else None

    return retry(push_once, attempts, transient, delay=lambda attempt: 0.2 * (attempt + 1))


def changes_before_merge(repo: Path) -> list[str]:
    code, out, err = git_try(repo, "rev-parse", "--verify", "--quiet", "MERGE_HEAD")
    if code == 0:
        return []
    if code != 1:
        raise RuntimeError((err or out).strip())
    code, out, err = git_try(repo, "status", "--porcelain", "-z", "--untracked-files=all", "--no-renames")
    if code:
        raise RuntimeError((err or out).strip())
    entries = [entry for entry in out.split("\0") if entry]
    if any("U" in entry[:2] or entry[:2] in ("AA", "DD") for entry in entries):
        return []
    return sorted({entry[3:] for entry in entries if entry[:2] not in ("??", "!!")})


def commit_paths(repo: Path, paths: list[str], message: str) -> list[str]:
    def checked(args: list[str]) -> str:
        code, out, err = git_try(repo, "--literal-pathspecs", *args)
        if code:
            raise RuntimeError((err or out).strip())
        return out

    paths = [path for path in paths if path != ".lokay" and not path.startswith(".lokay/")]
    if not paths:
        return []
    indexed = set(filter(None, checked(["ls-files", "-z", "--", *paths]).split("\0")))
    add_paths = [path for path in paths if path in indexed or (repo / path).exists() or (repo / path).is_symlink()]
    if add_paths:
        checked(["add", "--", *add_paths])
    staged = set(filter(None, checked(["diff", "--cached", "--name-only", "-z"]).split("\0")))
    committed = sorted(set(paths) & staged)
    if committed:
        checked(["commit", "--only", "-m", message, "--", *committed])
    return committed
