"""Commit only dirty Done-means stamp files (publish completeness brick)."""

from __future__ import annotations

from pathlib import Path

from lokay.git_commit import _commit_argv, _literal_pathspecs
from lokay.runner import Runner, git_spec
from lokay.stamp_paths import dirty_stamp_paths


def commit(worktree: str | Path, *, message: str, live: bool = True) -> dict:
    root = Path(worktree)
    if not live:
        return {"ok": True, "committed": False, "route": "planned", "planned": True}
    runner = Runner()
    porcelain = runner.run(
        git_spec(["status", "--porcelain", "-u"], cwd=root), live=True
    ).stdout
    dirty = dirty_stamp_paths(root, porcelain=porcelain)
    if not dirty:
        return {
            "ok": True,
            "committed": False,
            "route": "clean",
            "dirty_stamps": [],
        }
    pathspecs = _literal_pathspecs(dirty)
    runner.run_checked(git_spec(["add", "-A", "--", *pathspecs], cwd=root), live=True)
    status = runner.run(
        git_spec(["diff", "--cached", "--quiet", "--", *pathspecs], cwd=root),
        live=True,
    )
    if status.returncode == 0:
        return {
            "ok": True,
            "committed": False,
            "route": "clean",
            "dirty_stamps": dirty,
        }
    runner.run_checked(
        git_spec(
            [*_commit_argv("commit", "--only", "-m", message, "--", *pathspecs)],
            cwd=root,
        ),
        live=True,
    )
    commit = runner.run_checked(
        git_spec(["rev-parse", "HEAD"], cwd=root), live=True
    ).stdout.strip()
    return {
        "ok": True,
        "committed": True,
        "route": "committed",
        "commit": commit,
        "dirty_stamps": dirty,
    }
