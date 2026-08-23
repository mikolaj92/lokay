"""Run diff --no-index --check for one explicit untracked path."""

from pathlib import Path
from lokay.proc._common import runner
from lokay.runner import git_spec


def check(selected: dict) -> dict:
    out = runner().run(
        git_spec(
            ["diff", "--no-index", "--check", "--", "/dev/null", selected["path"]],
            cwd=Path(selected["worktree"]),
            timeout_seconds=120,
        ),
        live=True,
    )
    valid = out.returncode in {0, 1} and not (out.stderr or "").strip()
    return {
        **selected,
        "ok": valid,
        "route": "valid" if valid else "invalid",
        "error": "" if valid else "self-repair untracked diff check failed",
    }
