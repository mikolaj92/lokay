"""Recheck exact candidate identity after every test and diff validation."""

from pathlib import Path
from lokay.proc._common import runner
from lokay.runner import git_spec


def recheck(upstream: dict) -> dict:
    if not upstream.get("expected_subject"):
        return {**upstream, "ok": True, "validated_commit": ""}
    run = runner()
    path = Path(upstream["worktree"])
    status = run.run_checked(
        git_spec(["status", "--porcelain"], cwd=path), live=True
    ).stdout.strip()
    head = run.run_checked(
        git_spec(["rev-parse", "HEAD"], cwd=path), live=True
    ).stdout.strip()
    valid = not status and head == upstream.get("expected_commit")
    return {
        **upstream,
        "ok": valid,
        "validated_commit": head if valid else "",
        "error": "" if valid else "self-repair candidate changed during validation",
    }
