"""Read HEAD, ahead count, and subject for one exact candidate."""

from pathlib import Path
from lokay.proc._common import runner
from lokay.runner import git_spec


def inspect(request: dict) -> dict:
    run = runner()
    path = Path(request["worktree"])
    head = run.run_checked(
        git_spec(["rev-parse", "HEAD"], cwd=path), live=True
    ).stdout.strip()
    ahead = run.run_checked(
        git_spec(
            ["rev-list", "--count", f"{request['base_sha']}..HEAD"],
            cwd=path,
            timeout_seconds=120,
        ),
        live=True,
    ).stdout.strip()
    subject = run.run_checked(
        git_spec(["log", "-1", "--format=%s"], cwd=path), live=True
    ).stdout.strip()
    return {
        **request,
        "ok": True,
        "route": "identity",
        "head": head,
        "ahead": ahead,
        "subject": subject,
    }
