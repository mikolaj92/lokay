from __future__ import annotations

import subprocess
from pathlib import Path
from contextlib import contextmanager

from lokay.effects.pi import run_process
from lokay.safety import validate_argv

REF_LOCK = ("cannot lock ref", "unable to resolve reference", ".lock")


def _git(repo: Path, args: list[str], timeout: float = 60) -> tuple[int, str, str]:
    validate_argv(["git", *args])
    proc = run_process(["git", *args], cwd=repo, timeout=timeout)
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def worktree_add(repo: Path, branch: str, path: Path) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    code, out, err = _git(repo, ["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"])
    if code == 0:
        code, out, err = _git(repo, ["worktree", "add", str(path), branch])
    elif code == 1:
        code, out, err = _git(repo, ["fetch", "origin", "main"])
        if code != 0:
            return {"result": "failed", "error": err.strip() or out.strip()}
        code, out, err = _git(repo, ["worktree", "add", "-b", branch, str(path), "origin/main"])
    if code != 0:
        return {"result": "failed", "error": err.strip() or out.strip()}
    return {"result": "added", "path": str(path), "branch": branch}


def worktree_remove(repo: Path, path: Path) -> dict:
    code, out, err = _git(repo, ["worktree", "remove", "--force", str(path)])
    if code != 0 and path.exists():
        return {"result": "failed", "error": err.strip() or out.strip()}
    return {"result": "removed", "path": str(path)}


def worktree_prune(repo: Path) -> None:
    code, out, err = _git(repo, ["worktree", "prune"])
    if code:
        raise RuntimeError(err.strip() or out.strip())


def worktree_list(repo: Path) -> list[dict]:
    code, out, err = _git(repo, ["worktree", "list", "--porcelain", "-z"])
    if code:
        raise RuntimeError(err.strip() or out.strip())
    rows = []
    for block in out.split("\0\0"):
        row = {}
        for field in filter(None, block.split("\0")):
            key, _, value = field.partition(" ")
            row[key] = value
        if row:
            rows.append(row)
    return rows


def worktree_bytes(path: Path) -> int:
    proc = run_process(["du", "-sk", str(path)], timeout=120)
    if proc.returncode:
        raise RuntimeError(proc.stderr or "du failed")
    return int(proc.stdout.split()[0]) * 1024


def branch_delete(repo: Path, branch: str) -> None:
    code, out, err = _git(repo, ["branch", "-D", branch])
    if code:
        raise RuntimeError(err.strip() or out.strip())


def remote_sha(repo: Path, branch: str, *, strict: bool = False) -> str | None:
    code, out, err = _git(repo, ["ls-remote", "origin", f"refs/heads/{branch}"])
    if code != 0:
        if strict:
            raise RuntimeError(err.strip() or out.strip() or "remote lookup failed")
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
