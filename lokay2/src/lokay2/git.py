from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from lokay2.run import run_process
from lokay2.safety import validate_argv

REF_LOCK = ("cannot lock ref", "unable to resolve reference", ".lock")


def _git(repo: Path, args: list[str], timeout: float = 60) -> tuple[int, str, str]:
    validate_argv(["git", *args])
    proc = run_process(["git", *args], cwd=repo, timeout=timeout)
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def worktree_add(repo: Path, branch: str, path: Path) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    code, out, err = _git(repo, ["fetch", "origin", "main"])
    if code != 0:
        return {"result": "failed", "error": err.strip() or out.strip()}
    code, out, err = _git(repo, ["worktree", "add", "-b", branch, str(path), "origin/main"])
    if code != 0 and "already exists" not in (err + out):
        return {"result": "failed", "error": err.strip() or out.strip()}
    return {"result": "added", "path": str(path), "branch": branch}


def worktree_remove(repo: Path, path: Path) -> dict:
    code, out, err = _git(repo, ["worktree", "remove", "--force", str(path)])
    if code != 0 and path.exists():
        return {"result": "failed", "error": err.strip() or out.strip()}
    return {"result": "removed", "path": str(path)}


def reap_worktrees(repo: Path, root: Path, ttl_seconds: float, now: float | None = None) -> list[str]:
    stamp = time.time() if now is None else now
    removed: list[str] = []
    if not root.exists():
        return removed
    for child in root.iterdir():
        if not child.is_dir():
            continue
        age = stamp - child.stat().st_mtime
        if age < ttl_seconds:
            continue
        outcome = worktree_remove(repo, child)
        if outcome["result"] == "removed":
            removed.append(str(child))
            if child.exists():
                shutil.rmtree(child)
    return removed


def remote_sha(repo: Path, branch: str) -> str | None:
    code, out, err = _git(repo, ["ls-remote", "origin", f"refs/heads/{branch}"])
    if code != 0:
        return None
    line = out.strip().splitlines()
    if not line or not line[0].strip():
        return None
    return line[0].split()[0]


def push(repo: Path, branch: str, expected_remote_sha: str | None, attempts: int = 3) -> dict:
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
            head, _, _ = _git(repo, ["rev-parse", "HEAD"])
            _, sha, _ = _git(repo, ["rev-parse", "HEAD"])
            return {"result": "pushed", "sha": sha.strip(), "attempts": attempt} if head == 0 else {"result": "failed"}
        last = (err or out).lower()
        locked = any(mark in last for mark in REF_LOCK)
        if not locked or attempt == attempts:
            return {"result": "failed", "error": (err or out).strip()}
        time.sleep(0.2 * attempt)
    return {"result": "failed", "error": last}


def emit(payload: dict) -> None:
    print(json.dumps(payload, separators=(",", ":")))
