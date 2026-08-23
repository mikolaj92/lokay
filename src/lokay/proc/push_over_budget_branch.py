"""Push one committed over-budget branch."""

from lokay.passkit.support import run_proc
from lokay.proc import push_branch


def push(committed: dict, *, config_path: str | None, live: bool) -> dict:
    argv = (
        (["--config", config_path] if config_path else [])
        + (["--live"] if live else [])
        + [
            "--repo",
            committed["repo"],
            "--worktree",
            committed["worktree"],
            "--branch",
            committed["branch"],
        ]
    )
    out = run_proc(push_branch.main, argv)
    return {
        **committed,
        "route": "pushed" if out.get("ok") else "push_failed",
        "push": out,
    }
