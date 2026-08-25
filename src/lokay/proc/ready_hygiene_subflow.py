"""Invoke the authored ready-hygiene Fala."""

from lokay.graph_run import run_path


def run(*, config_path: str | None, live: bool) -> dict:
    return run_path(
        path_id="ready_hygiene",
        repo="local/ready-hygiene",
        config_path=config_path,
        live=live,
        max_ticks=16,
    )
