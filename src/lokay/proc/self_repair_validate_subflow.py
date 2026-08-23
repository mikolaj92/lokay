"""Invoke the authored self-repair candidate validation Fala."""

from lokay.graph_run import run_path


def run(
    *, worktree: str, base_sha: str, expected_subject: str, expected_commit: str
) -> dict:
    return run_path(
        path_id="self_repair_validate",
        repo="mikolaj92/lokay",
        max_ticks=256,
        extra_inputs={
            "worktree": worktree,
            "base_sha": base_sha,
            "expected_subject": expected_subject,
            "expected_commit": expected_commit,
        },
    )
