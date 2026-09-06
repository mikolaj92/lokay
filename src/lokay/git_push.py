from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from lokay.git_commit import is_configured_issue_worktree
from lokay.runner import Runner, git_spec

_REF_LOCK_MARKERS = (
    "cannot lock ref",
    "unable to resolve reference",
    "another git process seems to be running",
)


def is_configured_issue_branch(
    runner: Runner,
    worktree: Path,
    branch: str,
    configured_checkouts: Iterable[Path],
) -> bool:
    """Whether an issue worktree has exactly *branch* checked out."""
    if not is_configured_issue_worktree(runner, worktree, configured_checkouts):
        return False
    current = runner.run(
        git_spec(["symbolic-ref", "--quiet", "--short", "HEAD"], cwd=worktree),
        live=True,
    )
    return current.returncode == 0 and (current.stdout or "").strip() == branch


def is_ref_lock_error(text: str) -> bool:
    blob = str(text or "").lower()
    if any(marker in blob for marker in _REF_LOCK_MARKERS):
        return True
    return ".lock" in blob and "file exists" in blob


def _head_sha(runner: Runner, worktree: Path) -> str:
    result = runner.run(
        git_spec(["rev-parse", "HEAD"], cwd=worktree),
        live=True,
    )
    if result.returncode != 0:
        return ""
    return (result.stdout or "").strip()


def push_branch(
    runner: Runner,
    worktree: Path,
    branch: str,
    *,
    live: bool,
    attempts: int = 3,
    sleep_fn: Callable[[float], None] = time.sleep,
    sleep_seconds: float = 0.4,
) -> dict[str, Any]:
    """Push with bounded retry on ref-lock races (#1016). Never force-push.

    Returns a small envelope: ok, head_sha, attempts, and on failure reason.
    """
    tries = max(1, int(attempts))
    last_error = ""
    for attempt in range(1, tries + 1):
        try:
            runner.run_checked(
                git_spec(
                    ["push", "-u", "origin", branch],
                    cwd=worktree,
                    timeout_seconds=300,
                ),
                live=live,
            )
            return {
                "ok": True,
                "head_sha": _head_sha(runner, worktree),
                "attempts": attempt,
                "branch": branch,
            }
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            if not is_ref_lock_error(last_error) or attempt >= tries:
                reason = "ref_lock" if is_ref_lock_error(last_error) else "push_failed"
                return {
                    "ok": False,
                    "error": last_error,
                    "reason": reason,
                    "attempts": attempt,
                    "branch": branch,
                    "head_sha": _head_sha(runner, worktree),
                }
            sleep_fn(float(sleep_seconds) * attempt)
    return {
        "ok": False,
        "error": last_error or "push failed",
        "reason": "push_failed",
        "attempts": tries,
        "branch": branch,
        "head_sha": "",
    }
