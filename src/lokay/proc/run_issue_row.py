"""Nest one issue_row child Fala. One job: one catalog question, one issue_to_pr."""

from lokay.graph_run import run_path


def run(
    *,
    listed: dict,
    last: dict,
    config_path: str | None,
    live: bool,
    pass_dir: str,
) -> dict:
    return run_path(
        path_id="issue_row",
        repo="local/issue-row",
        config_path=config_path,
        live=live,
        extra_inputs={
            "pass_dir": pass_dir,
            "listed": listed,
            "last": last,
        },
    )
