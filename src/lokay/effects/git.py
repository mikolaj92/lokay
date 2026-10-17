from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from contextlib import contextmanager

from lokay.effects.pi import run_process
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

    def git(args):
        code, out, err = _git(path, args)
        if code:
            raise RuntimeError(err or out)
        return out.strip()

    root = Path(git(["rev-parse", "--show-toplevel"]))
    root_key = (root, branch)
    if root_key not in BASE_BRANCHES:
        common = (path / git(["rev-parse", "--git-common-dir"])).resolve()
        if common not in REPOSITORIES:
            code, out, err = _gh(["repo", "view", "--json", "nameWithOwner,defaultBranchRef"], cwd=root)
            if code == 0:
                REPOSITORIES[common] = json.loads(out)
        repo = REPOSITORIES.get(common, {})
        head = branch if branch is not None else git(["branch", "--show-current"])
        pr = open_pr_for(repo["nameWithOwner"], head) if head and repo else None
        base = (pr or {}).get("baseRefName") or (repo.get("defaultBranchRef") or {}).get("name")
        if not base:
            code, out, err = _git(path, ["symbolic-ref", "refs/remotes/origin/HEAD"])
            base = out.strip().removeprefix("refs/remotes/origin/") if code == 0 else ""
            base = base or "main"
        if common not in REPOSITORIES:
            return base
        BASE_BRANCHES[root_key] = base
    BASE_BRANCHES[key] = BASE_BRANCHES[root_key]
    return BASE_BRANCHES[root_key]


def _git(repo: Path, args: list[str], timeout: float = 60, *, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    validate_argv(["git", *args])
    proc = run_process(["git", *args], cwd=repo, timeout=timeout, env=env)
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def commit_time(repo: Path, ref: str) -> str:
    if not ref or ref.startswith("-") or any(char.isspace() for char in ref):
        raise ValueError("expected a git tag or sha")
    code, out, err = _git(repo, ["show", "-s", "--format=%cI", "--end-of-options", f"{ref}^{{commit}}", "--"])
    if code:
        raise ValueError(err.strip() or out.strip())
    return out.strip()


def merge_conflicts(repo: Path, sha: str) -> list[str]:
    if not isinstance(sha, str) or not re.fullmatch(r"[a-fA-F0-9]{7,64}", sha):
        raise ValueError("expected a hex sha of 7-64 characters")
    try:
        base = base_branch(repo)
        code, out, _ = _git(repo, ["merge-tree", "--write-tree", "--name-only", "-z", f"origin/{base}", sha])
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
    code, out, err = _git(repo, ["show", "--first-parent", "-m", "--name-only", "--format=", "-z", sha, "--"], env=env)
    if code or not out:
        code, out, err = _git(repo, ["diff-tree", "--name-only", "-r", "-z", f"{sha}^1", sha, "--"], env=env)
    if code:
        exists, _, error = _git(repo, ["rev-parse", "--verify", "--quiet", f"{sha}^{{object}}"], env=env)
        if exists == 1:
            return None
        raise ValueError(error.strip() if exists else err.strip() or out.strip())
    return [{"path": path} for path in dict.fromkeys(out.split("\0")) if path]


def ensure_worktree(repo: Path, branch: str, path: Path) -> dict:
    def checked(where, args):
        code, out, err = _git(where, args)
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
        matches = [row for row in records if row.get("worktree") == str(path)]
        if len(matches) != 1:
            raise ValueError("expected exactly one worktree registration")
        row = matches[0]
        if (row is records[0] or row.get("branch") != f"refs/heads/{branch}" or "bare" in row
                or "detached" in row or Path(row["worktree"]).resolve() == repo):
            raise ValueError("worktree registration or branch mismatch")
        if any(row.get("branch") == f"refs/heads/{branch}" and row.get("worktree") != str(path)
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
        if any(row.get("worktree") == str(path) for row in records):
            row = registration()
            if "locked" in row or path.exists() or path.is_symlink():
                raise ValueError("cannot recover locked or existing worktree")
            checked(repo, ["worktree", "remove", "--force", str(path)])
        if any(row.get("branch") == f"refs/heads/{branch}" for row in registrations()):
            raise ValueError("branch already registered at another worktree")
        code, out, err = _git(repo, ["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"])
        if code == 0:
            args = ["worktree", "add", str(path), branch]
        elif code == 1:
            code, out, err = _git(repo, ["ls-remote", "--exit-code", "--heads", "origin", f"refs/heads/{branch}"])
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


def worktree_add(repo: Path, branch: str, path: Path) -> dict:
    return ensure_worktree(repo, branch, path)


def worktree_remove(repo: Path, path: Path, *, safe: bool = False, branch: str | None = None) -> dict:
    if safe:
        def checked(where, args):
            code, out, err = _git(where, args)
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
            if checked(path, ["status", "--porcelain", "--untracked-files=all", "--ignored"]):
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
    code, out, err = _git(repo, ["worktree", "remove", "--force", str(path)])
    if code != 0 and path.exists():
        return {"result": "failed", "error": err.strip() or out.strip()}
    return {"result": "removed", "path": str(path)}


def remote_sha(repo: Path, branch: str) -> str | None:
    code, out, err = _git(repo, ["ls-remote", "origin", f"refs/heads/{branch}"])
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
    head_code, head_sha, _ = _git(repo, ["rev-parse", "HEAD"])
    if (
        expected_remote_sha
        and head_code == 0
        and current == head_sha.strip()
        and current == expected_remote_sha
    ):
        return {"result": "pushed", "sha": current, "attempts": 0}
    if current != expected_remote_sha:
        return {"result": "remote_moved", "sha": current or ""}
    last = ""
    for attempt in range(1, attempts + 1):
        code, out, err = _git(repo, ["push", "-u", "origin", branch], timeout=120)
        if code == 0:
            head, sha, _ = _git(repo, ["rev-parse", "HEAD"])
            return {"result": "pushed", "sha": sha.strip(), "attempts": attempt} if head == 0 else {"result": "failed"}
        last = (err or out).lower()
        locked = any(mark in last for mark in REF_LOCK)
        if not locked or attempt == attempts:
            return {"result": "failed", "error": (err or out).strip()}
        from lokay.effects.pi import retry_sleep

        retry_sleep(0.2 * attempt)
    return {"result": "failed", "error": last}


def commit_paths(repo: Path, paths: list[str], message: str) -> list[str]:
    def checked(args: list[str]) -> str:
        code, out, err = _git(repo, ["--literal-pathspecs", *args])
        if code:
            raise RuntimeError((err or out).strip())
        return out

    paths = [path for path in paths if path != ".lokay" and not path.startswith(".lokay/")]
    if not paths:
        return []
    checked(["add", "--", *paths])
    staged = set(filter(None, checked(["diff", "--cached", "--name-only", "-z"]).split("\0")))
    committed = sorted(set(paths) & staged)
    if committed:
        checked(["commit", "--only", "-m", message, "--", *committed])
    return committed


def command(repo: Path, args: list[str], *, timeout: float = 30):
    return run_process(["git", *args], cwd=repo, timeout=timeout)


class PiGitViolation(RuntimeError):
    def failure(self) -> dict:
        return {"result": "failed", "reason": "pi_git_changed", "explanation": str(self), "artifact": ""}


@contextmanager
def pi_git_guard(path: Path):
    def checked(args):
        proc = command(path, args)
        if proc.returncode != 0:
            raise PiGitViolation(f"pi git checks failed: {proc.stderr.strip()}")
        return proc.stdout

    head = checked(["rev-parse", "HEAD"]).strip()
    refs = checked(["for-each-ref"])
    try:
        yield
    finally:
        from lokay.effects.pi import tick_deadline

        token = tick_deadline.set(None)
        try:
            after = checked(["rev-parse", "HEAD"]).strip()
            after_refs = checked(["for-each-ref"])
            commits = checked(["rev-list", "HEAD", f"^{head}", "--"])
            if after != head or after_refs != refs or commits.strip():
                raise PiGitViolation("pi changed git HEAD or refs, or created commits beyond its pre-run HEAD")
        finally:
            tick_deadline.reset(token)


def guarded_command(path: Path, *args: str, input: bytes | None = None) -> bytes:
    return subprocess.run(
        ["git", "--literal-pathspecs", "-C", str(path), *args], input=input,
        capture_output=True, check=True, timeout=60,
    ).stdout


def path_at_head(path: Path, head: str, name: str) -> bool:
    return subprocess.run(
        ["git", "-C", str(path), "cat-file", "-e", f"{head}:{name}"],
        capture_output=True, timeout=60,
    ).returncode == 0


def _snapshot(path: Path) -> dict:
    status = guarded_command(path, "status", "--porcelain", "-z", "--untracked-files=all")
    head = guarded_command(path, "rev-parse", "HEAD").decode().strip()
    names = set(guarded_command(path, "diff", "--name-only", "-z").split(b"\0"))
    names.update(guarded_command(path, "diff", "--cached", "--name-only", "-z").split(b"\0"))

    patches = {
        name.decode(): (
            guarded_command(path, "diff", "--binary", "--cached", "--", name.decode()),
            guarded_command(path, "diff", "--binary", "--", name.decode()),
        )
        for name in names if name
    }
    untracked = set(guarded_command(path, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0")) - {b""}
    return {"status": status, "head": head, "patches": patches, "untracked": untracked}


def restore_changes(snapshots: dict[Path, dict]) -> dict:
    report = {"changed": False, "paths": [], "files": []}
    for path, before in snapshots.items():
        after = _snapshot(path)
        moved = after["head"] != before["head"]
        files = {
            name for name in before["patches"].keys() | after["patches"].keys()
            if before["patches"].get(name) != after["patches"].get(name)
        }
        if moved:
            files.update(name.decode() for name in guarded_command(
                path, "diff", "--name-only", "-z", before["head"], after["head"],
            ).split(b"\0") if name)
        new = after["untracked"] - before["untracked"]
        changed = moved or after["status"] != before["status"] or bool(files)
        if not changed:
            continue
        report["changed"] = True
        report["paths"].append(str(path))
        report["files"].extend(f"{path}/{name}" for name in sorted(files | {n.decode() for n in new}))
        if moved and not before["status"]:
            guarded_command(path, "reset", "--hard", before["head"])
        else:

            for name in sorted(files):
                exists = path_at_head(path, before["head"], name)
                if exists:
                    guarded_command(path, "checkout", before["head"], "--", name)
                elif name.encode() in before["untracked"]:
                    guarded_command(path, "rm", "--cached", "-f", "--ignore-unmatch", "--", name)
                else:
                    guarded_command(path, "rm", "-f", "--ignore-unmatch", "--", name)
                staged, unstaged = before["patches"].get(name, (b"", b""))
                if staged:
                    guarded_command(path, "apply", "--binary", "--index", input=staged)
                if unstaged:
                    guarded_command(path, "apply", "--binary", input=unstaged)
        for name in sorted(new):
            guarded_command(path, "--literal-pathspecs", "clean", "-fd", "--", name.decode())
    return report


@contextmanager
def guard(paths):
    snapshots = {Path(path).expanduser().resolve(): None for path in paths if path is not None}
    snapshots = {path: _snapshot(path) for path in snapshots}
    report = {"changed": False, "paths": [], "files": []}
    try:
        yield report
    finally:
        report.update(restore_changes(snapshots))


def failure(report: dict, worktree: Path) -> dict:
    details = "; ".join(
        f"{path}: {', '.join(name.removeprefix(path + '/') for name in report['files'] if name.startswith(path + '/')) or 'HEAD/status'}"
        for path in report["paths"]
    )
    return {
        "result": "failed", "reason": "outside_worktree",
        "explanation": f"pi modified {details}; restored. Work only inside {worktree}.",
        "artifact": str(worktree),
        "paths": report["paths"], "files": report["files"],
    }
