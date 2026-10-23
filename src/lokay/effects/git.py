from __future__ import annotations

import os
import re
import shutil
from uuid import uuid4
from subprocess import CompletedProcess, TimeoutExpired
from typing import Any
from pathlib import Path

from lokay import store
from lokay.effects.pi import run_process
from lokay.effects.retry import retry
from lokay.safety import validate_argv

REF_LOCK = ("cannot lock ref", "unable to resolve reference", ".lock")
BASE_BRANCHES: dict[tuple[Path, str | None], str] = {}
REPOSITORIES: dict[Path, dict] = {}


def samefile(left: str | Path, right: str | Path) -> bool:
    try:
        return os.path.samefile(left, right)
    except OSError:
        return False


def worktree_record_matches(record: str, path: Path) -> bool:
    return any(samefile(field.removeprefix("worktree "), path)
               for field in record.split("\0") if field.startswith("worktree "))


def base_branch(path: Path, *, branch: str | None = None) -> str:
    path = path.resolve()
    key = (path, branch)
    if key in BASE_BRANCHES:
        return BASE_BRANCHES[key]
    from lokay.effects.gh import _gh, open_pr_for
    import json

    root = Path(git(path, "rev-parse", "--show-toplevel", timeout=60))
    root_key = (root, branch)
    if root_key not in BASE_BRANCHES:
        common = (path / git(path, "rev-parse", "--git-common-dir", timeout=60)).resolve()
        if common not in REPOSITORIES:
            code, out, err = _gh(["repo", "view", "--json", "nameWithOwner,defaultBranchRef"], cwd=root)
            if code == 0:
                REPOSITORIES[common] = json.loads(out)
        repo = REPOSITORIES.get(common, {})
        head = branch if branch is not None else git(path, "branch", "--show-current", timeout=60)
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


def checkout_version() -> str | None:
    root = Path(os.environ.get("LOKAY_ROOT") or Path(__file__).resolve().parents[3])
    try:
        return git(root, "rev-parse", "HEAD") or None
    except (OSError, RuntimeError, TimeoutExpired):
        return None


def lsof_path() -> str | None:
    return shutil.which("lsof", path=os.environ.get("PATH", os.defpath) + os.pathsep + "/usr/sbin:/sbin")


def _remove_stale_lock(repo: Path, stderr: str) -> bool:
    match = re.search(r"Unable to create '([^']+\.lock)': File exists", stderr)
    if not match:
        return False
    lock = repo / match[1]
    try:
        if not lock.is_file():
            return False
        lsof = lsof_path()
        if lsof is None:
            return False
        proc = run_process([lsof, "-t", "--", str(lock)], timeout=10)
        if proc.returncode == 0 and (proc.stdout or "").strip():
            return False
        lock.unlink(missing_ok=True)
    except (OSError, TimeoutExpired):
        return False
    return True


def git_try(path: Path, *args: str, timeout: float = 60, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    proc = _command(path, list(args), timeout=timeout, env=env)
    if proc.returncode != 0 and _remove_stale_lock(path, proc.stderr or ""):
        proc = _command(path, list(args), timeout=timeout, env=env)
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def git(path: Path, *args: str, timeout: float = 30) -> str:
    code, out, err = git_try(path, *args, timeout=timeout)
    if code:
        raise RuntimeError((err or out).strip())
    return out.strip()


def gate_tasks(worktree: Path, base: str, sha: str, rows: list[dict]) -> list[dict]:
    from lokay.gates import gate_location
    from lokay.types import parse_finding
    import shlex

    revision = git(worktree, "merge-base", f"origin/{base}", sha)
    tasks = []
    for row in rows:
        path, line, kind = gate_location(row)
        target = worktree / path
        if Path(path).is_absolute() or not target.resolve().is_relative_to(worktree.resolve()) or ".git" in Path(path).parts:
            raise ValueError("gate path outside worktree")
        exists = bool(git(worktree, "--literal-pathspecs", "ls-tree", "--name-only", revision, "--", path))
        if kind == "no_new_comments":
            noun = "docstring" if "docstring" in parse_finding(row).zmiana.lower() else "comment"
            instruction = f"MUST delete the {noun} at {path}:{line}; change nothing else"
        elif kind == "weakened_tests" or exists:
            instruction = (f"MUST restore {path}:{line} to merge-base {revision[:12]} "
                           f"(git --literal-pathspecs checkout {revision} -- {shlex.quote(path)}); "
                           "do not change or remove its assertions")
        else:
            instruction = f"MUST remove the generated file {path}:{line}"
        tasks.append({**row, "instruction": instruction, "gate_base": revision, "gate_exists": exists})
    return tasks


def revert_gates(worktree: Path, rows: list[dict]) -> None:
    from lokay.gates import gate_location, remove_comment

    grouped = {}
    for row in rows:
        path, line, kind = gate_location(row)
        grouped.setdefault(path, []).append((line, kind, row))
    for path, entries in grouped.items():
        target = worktree / path
        restores = [row for _, kind, row in entries if kind != "no_new_comments"]
        if restores:
            row = restores[0]
            if row["gate_exists"] or gate_location(row)[2] == "weakened_tests":
                git(worktree, "--literal-pathspecs", "checkout", row["gate_base"], "--", path)
            else:
                git(worktree, "--literal-pathspecs", "rm", "-f", "--", path)
        elif target.is_file():
            source = target.read_bytes().decode()
            for line, _, _ in sorted(entries, key=lambda entry: entry[0], reverse=True):
                source = remove_comment(source, line, target.suffix in {".py", ".pyi"})
            store.write_artifact(target, source.encode())


def restart_from_base(worktree: Path, base: str) -> None:
    ref = f"origin/{base}"
    commit = git(worktree, "commit-tree", f"{ref}^{{tree}}", "-p", "HEAD", "-p", ref,
                 "-m", f"lokay: restart from {ref}")
    git(worktree, "reset", "--hard", commit, timeout=300)


def merge_base_or_restart(worktree: Path, base: str) -> list[str]:
    ref = f"origin/{base}"
    code, out, err = git_try(worktree, "merge", "--no-edit", ref, timeout=300)
    if code == 0:
        return []
    if code != 1:
        raise RuntimeError((err or out).strip())
    conflicts = list(filter(None, git(worktree, "diff", "--name-only", "--diff-filter=U", "-z").split("\0")))
    if not conflicts:
        raise RuntimeError((err or out).strip())
    git(worktree, "merge", "--abort", timeout=300)
    restart_from_base(worktree, base)
    return conflicts


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
                   if row.get("worktree") is not None and samefile(row["worktree"], path)]
        if len(matches) != 1:
            raise ValueError("expected exactly one worktree registration")
        row = matches[0]
        if (row is records[0] or row.get("branch") != f"refs/heads/{branch}" or "bare" in row
                or "detached" in row or samefile(row["worktree"], repo)):
            raise ValueError("worktree registration or branch mismatch")
        if any(row.get("branch") == f"refs/heads/{branch}"
               and (row.get("worktree") is None or not samefile(row["worktree"], path))
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
        if (not samefile(top, path) or not samefile(path / common, common_dir)
                or not samefile(git_dir.parent, common_dir / "worktrees") or head != f"refs/heads/{branch}"):
            raise ValueError("worktree top-level, common directory or branch mismatch")

    try:
        checked(repo, ["check-ref-format", "--branch", branch])
        match = re.fullmatch(r"lokay/([1-9][0-9]*)", branch)
        if not match:
            raise ValueError("expected lokay/<positive decimal issue>")
        repo = repo.resolve()
        path = path.parent.resolve() / path.name
        expected = repo.parent / f"{repo.name}-wt-{match[1]}"
        if path.is_symlink() or path != expected or samefile(path, repo):
            raise ValueError(f"expected non-symlink sibling worktree path {expected}")
        if not samefile(checked(repo, ["rev-parse", "--show-toplevel"]).strip(), repo):
            raise ValueError("repository top-level mismatch")
        common_dir = (repo / checked(repo, ["rev-parse", "--git-common-dir"]).strip()).resolve()
        if path.exists():
            verify()
            return {"result": "added", "path": str(path), "branch": branch}
        records = registrations()
        if any(row.get("worktree") is not None and samefile(row["worktree"], path)
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


def detached_worktree(root: Path, path: Path, start: str) -> None:
    if path.exists():
        worktree_remove(root, path)
    store.ensure_directory(path.parent)
    git(root, "worktree", "add", "--detach", str(path), start, timeout=300)


def worktree_patch(worktree: Path) -> str:
    names = git(worktree, "ls-files", "--others", "--exclude-standard", "-z").split("\0")
    for name in filter(None, names):
        git(worktree, "--literal-pathspecs", "add", "--intent-to-add", "--", name)
    code, out, err = git_try(worktree, "diff", "--binary", "HEAD", timeout=300)
    if code:
        raise RuntimeError(err or "patch export failed")
    return out


def apply_patch(worktree: Path, patch: Path) -> None:
    code, _, _ = git_try(worktree, "apply", "--reverse", "--check", str(patch))
    if code == 0:
        return
    git(worktree, "apply", "--index", str(patch), timeout=300)


def restore_head(worktree: Path) -> None:
    git(worktree, "reset", "--hard", "HEAD", timeout=300)


def plan_checkout(root: Path) -> Path:
    root = root.resolve()
    path = root.parent / f"{root.name}-plan"
    if path.is_symlink():
        raise ValueError("expected non-symlink plan checkout")
    if not samefile(git(root, "rev-parse", "--show-toplevel"), root):
        raise ValueError("plan checkout repository mismatch")
    base = base_branch(root)
    common = (root / git(root, "rev-parse", "--git-common-dir")).resolve()
    if not path.exists():
        git(root, "worktree", "add", "--detach", str(path), f"origin/{base}", timeout=60)
    if not (path / ".git").is_file() or (path / ".git").is_symlink():
        raise ValueError("expected a registered linked plan checkout")
    records = git(root, "worktree", "list", "--porcelain", "-z").split("\0\0")
    matches = [record.split("\0") for record in records if worktree_record_matches(record, path)]
    if (len(matches) != 1 or "detached" not in matches[0]
            or any(field.startswith("locked") for field in matches[0])):
        raise ValueError("plan checkout registration mismatch or locked")
    git_dir = (path / git(path, "rev-parse", "--git-dir")).resolve()
    if (not samefile(git(path, "rev-parse", "--show-toplevel"), path)
            or not samefile(path / git(path, "rev-parse", "--git-common-dir"), common)
            or not samefile(git_dir.parent, common / "worktrees")):
        raise ValueError("plan checkout repository mismatch")
    git(path, "checkout", "--detach", "--force", f"origin/{base}", timeout=60)
    git(path, "clean", "-fdx", timeout=60)
    BASE_BRANCHES[(path, None)] = base
    return path


def worktree_remove(repo: Path, path: Path, *, safe: bool = False, branch: str | None = None,
                    patch_path: Path | None = None) -> dict:
    def remove():
        renamed = path.with_name(f".{path.name}.removing-{uuid4().hex}")
        os.rename(path, renamed)
        code, out, err = git_try(repo, "worktree", "prune", "--expire=now")
        if code:
            raise RuntimeError(err.strip() or out.strip() or "worktree prune failed")
        try:
            shutil.rmtree(renamed)
        except OSError:
            pass

    if safe:
        def checked(where, args):
            code, out, err = git_try(where, *args)
            if code:
                raise RuntimeError(err.strip() or out.strip() or "cleanup lookup failed")
            return out.strip()

        def archive(where, ref="HEAD"):
            code, upstream, _ = git_try(where, "rev-parse", "--verify", f"{ref}@{{upstream}}")
            base = upstream.strip() if code == 0 else f"origin/{base_branch(repo)}"
            refs = [base, ref] if where == repo else [base]
            proc = _command(where, ["diff", "--binary", *refs, "--"], timeout=60, text=False)
            if proc.returncode:
                raise RuntimeError(proc.stderr.decode(errors="replace").strip() or "cleanup diff failed")
            diff = proc.stdout
            if where != repo:
                code, untracked, err = git_try(where, "ls-files", "--others", "--exclude-standard", "-z")
                if code:
                    raise RuntimeError(err.strip() or "cleanup untracked lookup failed")
                for name in filter(None, untracked.split("\0")):
                    proc = _command(where, ["diff", "--binary", "--no-index", "--", "/dev/null", name],
                                    timeout=60, text=False)
                    if proc.returncode not in (0, 1):
                        raise RuntimeError(proc.stderr.decode(errors="replace").strip() or "cleanup untracked diff failed")
                    diff += proc.stdout
            store.write_artifact(patch_path, diff)

        try:
            match = re.fullmatch(r"lokay/([1-9][0-9]*)", branch or "")
            if not match:
                raise ValueError("expected lokay/<positive decimal issue>")
            repo = repo.resolve()
            path = path.parent.resolve() / path.name
            expected = repo.parent / f"{repo.name}-wt-{match[1]}"
            if path != expected or path.is_symlink() or samefile(path, repo):
                raise ValueError("expected non-symlink sibling worktree path")
            ref = f"refs/heads/{branch}"
            if not path.exists():
                if not samefile(checked(repo, ["rev-parse", "--show-toplevel"]), repo):
                    raise ValueError("repository top-level mismatch")
                records = checked(repo, ["worktree", "list", "--porcelain", "-z"]).split("\0\0")
                matches = [record.split("\0") for record in records
                           if worktree_record_matches(record, path)]
                if any(f"branch {ref}" in record.split("\0")
                       and not worktree_record_matches(record, path) for record in records):
                    return {"result": "kept", "path": str(path), "reason": "branch checked out"}
                if matches:
                    if (len(matches) != 1 or f"branch {ref}" not in matches[0]
                            or any(field.startswith("locked") for field in matches[0])):
                        raise ValueError("worktree registration mismatch or locked")
                    checked(repo, ["worktree", "prune", "--expire=now"])
                    records = checked(repo, ["worktree", "list", "--porcelain", "-z"]).split("\0\0")
                if any(f"branch {ref}" in record.split("\0") for record in records):
                    return {"result": "kept", "path": str(path), "reason": "branch checked out"}
                code, head, err = git_try(repo, "rev-parse", "--verify", "--quiet", ref)
                if code == 1:
                    return {"result": "removed", "path": str(path)}
                if code:
                    raise RuntimeError(err.strip() or head.strip() or "cleanup lookup failed")
                head = head.strip()
                if not checked(repo, ["for-each-ref", f"--contains={head}",
                                      "--format=%(refname)", "refs/remotes/origin/"]):
                    if patch_path is None:
                        return {"result": "kept", "path": str(path), "reason": "unpushed"}
                    archive(repo, ref)
                checked(repo, ["update-ref", "-d", ref, head])
                return {"result": "removed", "path": str(path)}
            if (not samefile(checked(repo, ["rev-parse", "--show-toplevel"]), repo)
                    or not (path / ".git").is_file() or (path / ".git").is_symlink()
                    or not samefile(checked(path, ["rev-parse", "--show-toplevel"]), path)
                    or checked(path, ["symbolic-ref", "HEAD"]) != ref):
                raise ValueError("worktree top-level or branch mismatch")
            common = (repo / checked(repo, ["rev-parse", "--git-common-dir"])).resolve()
            if not samefile(path / checked(path, ["rev-parse", "--git-common-dir"]), common):
                raise ValueError("worktree repository mismatch")
            records = checked(repo, ["worktree", "list", "--porcelain", "-z"]).split("\0\0")
            matches = [record.split("\0") for record in records
                       if worktree_record_matches(record, path)]
            if (len(matches) != 1 or f"branch {ref}" not in matches[0]
                    or any(field.startswith("locked") for field in matches[0])):
                raise ValueError("worktree registration mismatch or locked")
            dirty = checked(path, ["status", "--porcelain", "--untracked-files=all"])
            if dirty and patch_path is None:
                return {"result": "kept", "path": str(path), "reason": "dirty"}
            head = checked(repo, ["rev-parse", "--verify", ref])
            if checked(path, ["rev-parse", "HEAD"]) != head:
                raise ValueError("worktree HEAD mismatch")
            reachable = checked(repo, ["for-each-ref", f"--contains={head}",
                                       "--format=%(refname)", "refs/remotes/origin/"])
            if patch_path is not None and (dirty or not reachable):
                archive(path)
            remove()
            if reachable or patch_path is not None:
                checked(repo, ["update-ref", "-d", ref, head])
            return {"result": "removed", "path": str(path)}
        except (OSError, ValueError, RuntimeError) as exc:
            return {"result": "failed", "error": str(exc)}
    if not path.exists():
        code, out, err = git_try(repo, "worktree", "remove", "--force", str(path))
        if code != 0 and path.exists():
            return {"result": "failed", "error": err.strip() or out.strip()}
        return {"result": "removed", "path": str(path)}
    try:
        remove()
    except (OSError, RuntimeError) as exc:
        return {"result": "failed", "error": str(exc)}
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
        if not current or git_try(repo, "merge-base", "--is-ancestor", current, "HEAD")[0] != 0:
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
