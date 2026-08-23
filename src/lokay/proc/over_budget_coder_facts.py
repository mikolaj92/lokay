"""Physical process and worktree facts for one detached coder."""

import subprocess
from pathlib import Path
from lokay.git_real_diff import classify_changed_paths, list_changed_paths
from lokay.proc._common import runner
from lokay.proc.detach_issue_to_pr import _child_pids, _pid_command, is_coding_command


def process_cwd(pid: int) -> Path | None:
    try:
        return Path(f"/proc/{int(pid)}/cwd").resolve(strict=True)
    except OSError:
        pass
    try:
        done = subprocess.run(
            ["lsof", "-a", "-p", str(int(pid)), "-d", "cwd", "-Fn"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if done.returncode:
        return None
    return next(
        (
            Path(x[1:])
            for x in (done.stdout or "").splitlines()
            if x.startswith("n") and len(x) > 1
        ),
        None,
    )


def coder_worktree(pid: int) -> Path | None:
    seen = set()
    stack = [(int(pid), 0)]
    coders = []
    while stack:
        current, depth = stack.pop()
        if current <= 0 or current in seen:
            continue
        seen.add(current)
        if current != int(pid) and is_coding_command(_pid_command(current)):
            coders.append((depth, current))
        stack.extend((child, depth + 1) for child in _child_pids(current))
    if not coders:
        return None
    deepest = max(x[0] for x in coders)
    worktree = next((process_cwd(x[1]) for x in coders if x[0] == deepest), None)
    return worktree if worktree and worktree.is_dir() else None


def coder_diff(pid: int) -> dict:
    worktree = coder_worktree(pid)
    if worktree is None:
        return {"kind": "unknown", "worktree": ""}
    try:
        kind = classify_changed_paths(
            list_changed_paths(runner(), worktree, base="origin/main")
        )
    except Exception:
        return {"kind": "unknown", "worktree": str(worktree)}
    return {"kind": kind, "worktree": str(worktree)}


def worktree_branch(worktree: str) -> str:
    if not worktree:
        return ""
    try:
        done = subprocess.run(
            ["git", "-C", worktree, "symbolic-ref", "--quiet", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return (done.stdout or "").strip() if done.returncode == 0 else ""
