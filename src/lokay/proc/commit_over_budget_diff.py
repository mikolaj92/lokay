"""Commit one harvested real diff."""

from lokay.passkit.support import run_proc
from lokay.proc import commit_all


def commit(route: dict, *, config_path: str | None, live: bool) -> dict:
    argv = (
        (["--config", config_path] if config_path else [])
        + (["--live"] if live else [])
        + [
            "--repo",
            route["repo"],
            "--worktree",
            route["worktree"],
            "--message",
            f"fix: {route['repo']}#{route['issue']}",
        ]
    )
    out = run_proc(commit_all.main, argv)
    return {
        **route,
        "route": "committed" if out.get("ok") else "commit_failed",
        "commit": out,
    }
