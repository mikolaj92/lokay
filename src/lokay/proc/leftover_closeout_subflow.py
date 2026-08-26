"""Invoke the authored leftover-closeout Fala."""

from lokay.graph_run import run_path


def run(*, config_path: str | None, live: bool) -> dict:
    return run_path(
        path_id="leftover_closeout",
        repo="local/leftover-closeout",
        config_path=config_path,
        live=live,
        max_ticks=16,
    )
