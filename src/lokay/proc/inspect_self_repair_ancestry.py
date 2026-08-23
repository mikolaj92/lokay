"""Read whether current origin/main is an ancestor of the candidate HEAD."""

from pathlib import Path
from lokay.proc._common import runner
from lokay.runner import git_spec


def inspect(candidate: dict) -> dict:
    ancestor = (
        runner()
        .run(
            git_spec(
                ["merge-base", "--is-ancestor", candidate["base_sha"], "HEAD"],
                cwd=Path(candidate["worktree"]),
                timeout_seconds=60,
            ),
            live=True,
        )
        .returncode
        == 0
    )
    if ancestor:
        return {
            **candidate,
            "route": "resume",
            "candidate_commit": (
                candidate.get("head") if int(candidate.get("ahead") or 0) > 0 else ""
            ),
        }
    if candidate.get("uncommitted") == "empty" and int(candidate.get("ahead") or 0) > 0:
        return {**candidate, "route": "remove"}
    return {
        **candidate,
        "route": "error",
        "error": "cannot resume self-repair worktree outside current origin/main",
    }
