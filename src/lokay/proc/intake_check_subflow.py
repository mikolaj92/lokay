"""Invoke authored one mechanical intake-check Fala."""

from lokay.graph_run import run_path


def run(
    *,
    config_path: str | None,
    live: bool,
    repo: str,
    issue: int,
    check: str,
    merged_prs: list[int] | None = None,
    tracker_done: bool = False,
    covering_prs: list[str] | None = None,
) -> dict:
    return run_path(
        path_id="intake_check_execution",
        repo=repo,
        issue=issue,
        config_path=config_path,
        live=False,
        max_ticks=40,
        extra_inputs={
            "config_path": config_path or "",
            "live": live,
            "repo": repo,
            "issue": issue,
            "check": check,
            "merged_prs": merged_prs or [],
            "tracker_done": tracker_done,
            "covering_prs": covering_prs or [],
        },
    )
