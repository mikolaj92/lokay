"""Collect whether the current resumed issue branch already contains source code."""

from __future__ import annotations
import re
from pathlib import Path
from lokay.runner import CommandSpec


def collect(*, runner, repo: str, issue: int, cwd: Path, live: bool) -> dict:
    if not live:
        return {"ok": True, "resumed_source": False}

    def run(*argv):
        return runner.run(
            CommandSpec(tuple(argv), cwd=str(cwd), timeout_seconds=20), live=True
        )

    try:
        branch = run("git", "branch", "--show-current").stdout.strip()
        remote = (
            run("git", "remote", "get-url", "origin")
            .stdout.strip()
            .removesuffix(".git")
        )
        changed = run(
            "git", "diff", "--name-only", "origin/main...HEAD"
        ).stdout.splitlines()
    except Exception:
        return {"ok": True, "resumed_source": False, "probe_failed": True}
    match = (
        (remote.endswith(f"github.com/{repo}") or remote.endswith(f":{repo}"))
        and re.search(rf"(?:^|[/_-]){issue}(?:$|[/_-])", branch) is not None
        and any(p.startswith("src/") for p in changed)
    )
    return {"ok": True, "resumed_source": bool(match), "branch": branch}
