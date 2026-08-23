"""Close out one issue whose delivery PR already exists."""

from __future__ import annotations
from lokay.proc.closeout import run_closeout


def close(*, repo: str, issue: int, config_path: str | None, live: bool) -> dict:
    return run_closeout(repo=repo, issue=issue, config_path=config_path, live=live)
