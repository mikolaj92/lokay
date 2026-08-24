"""Invoke authored one-issue stage transition Fala."""

from lokay.graph_run import run_path


def run(
    *,
    config_path: str | None,
    live: bool,
    repo: str,
    issue: int,
    stage: str,
    receipt: bool = False,
    comment: str = "",
) -> dict:
    return run_path(
        path_id="stage_label_execution",
        repo=repo,
        issue=issue,
        config_path=config_path,
        live=live,
        max_ticks=40,
        extra_inputs={
            "config_path": config_path or "",
            "live": live,
            "repo": repo,
            "issue": issue,
            "stage": stage,
            "receipt": receipt,
            "comment": comment,
        },
    )
