"""Read whether current origin/main is an ancestor of the candidate HEAD."""

from pathlib import Path
from lokay.proc._common import runner
from lokay.proc.read_self_repair_validation_outcome import read_for_head
from lokay.runner import git_spec


def inspect(candidate: dict) -> dict:
    outcome = read_for_head(candidate)
    if outcome.get("test_timed_out") is True:
        return {
            **candidate,
            "route": "remove",
            "error": "cannot resume self-repair candidate whose validation timed out",
        }
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
