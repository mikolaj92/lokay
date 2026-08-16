"""Fetch origin/<base> and rebase the mill corner onto it.

Force-push is forbidden. A conflict is fail-closed: abort the rebase and
refuse to publish. The next pass re-implements from current main.
"""

from __future__ import annotations

from pathlib import Path

from lokay.runner import Runner, git_spec


class RebaseConflict(RuntimeError):
    """Replay onto origin/<base> stopped; worktree is aborted back."""

    def __init__(self, detail: str = "") -> None:
        self.reason = "rebase_conflict"
        msg = "rebase onto origin/base conflicted"
        if detail:
            msg = f"{msg}: {detail}"
        super().__init__(msg)


class RebaseError(RuntimeError):
    """Fetch or rebase plumbing failed closed (not a content conflict)."""

    def __init__(self, message: str, *, reason: str) -> None:
        self.reason = reason
        super().__init__(message)


def _rev_count(runner: Runner, worktree: Path, spec: str) -> int | None:
    result = runner.run(
        git_spec(["rev-list", "--count", spec], cwd=worktree, timeout_seconds=60),
        live=True,
    )
    if result.returncode != 0:
        return None
    try:
        return int((result.stdout or "").strip() or "0")
    except ValueError:
        return None


def rebase_onto_base(
    runner: Runner,
    worktree: Path,
    *,
    live: bool,
    base: str = "main",
) -> dict[str, object]:
    """Replay HEAD onto ``origin/<base>``. Never force-push.

    Returns a receipt. Raises ``RebaseConflict`` when git cannot replay;
    raises ``RebaseError`` when fetch / measurement fails.
    """
    if not live:
        return {
            "rebased": False,
            "planned": True,
            "already_current": False,
            "base": base,
        }

    fetched = runner.run(
        git_spec(["fetch", "origin", base], cwd=worktree, timeout_seconds=300),
        live=True,
    )
    if fetched.returncode != 0:
        detail = (fetched.stderr or fetched.stdout or "").strip()
        raise RebaseError(
            f"cannot fetch origin/{base}: {detail}",
            reason="fetch_failed",
        )

    behind = _rev_count(runner, worktree, f"HEAD..origin/{base}")
    if behind is None:
        raise RebaseError(
            f"cannot measure behind vs origin/{base}",
            reason="rebase_behind_unreadable",
        )
    if behind == 0:
        return {
            "rebased": False,
            "planned": False,
            "already_current": True,
            "base": base,
            "behind": 0,
        }

    replayed = runner.run(
        git_spec(["rebase", f"origin/{base}"], cwd=worktree, timeout_seconds=180),
        live=True,
    )
    if replayed.returncode == 0:
        return {
            "rebased": True,
            "planned": False,
            "already_current": False,
            "base": base,
            "behind": behind,
        }

    runner.run(
        git_spec(["rebase", "--abort"], cwd=worktree, timeout_seconds=60),
        live=True,
    )
    detail = (replayed.stderr or replayed.stdout or "").strip()
    raise RebaseConflict(detail)
