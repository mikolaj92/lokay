"""Run one explicit tracked diff --check variant."""

from pathlib import Path
from lokay.proc._common import runner
from lokay.runner import git_spec


def check(upstream: dict, *, kind: str) -> dict:
    args = {
        "working": ["diff", "--check"],
        "cached": ["diff", "--cached", "--check"],
        "committed": ["diff", "--check", f"{upstream['base_sha']}...HEAD"],
    }[kind]
    out = runner().run(
        git_spec(args, cwd=Path(upstream["worktree"]), timeout_seconds=120), live=True
    )
    valid = out.returncode == 0
    return {
        **upstream,
        "ok": valid,
        "route": "valid" if valid else "invalid",
        "error": "" if valid else "self-repair diff check failed",
    }
