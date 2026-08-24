"""Invoke the authored factory-begin Fala."""

from lokay.graph_run import run_path


def run(*, config_path: str | None, live: bool) -> dict:
    return run_path(
        path_id="factory_begin",
        repo="local/factory-begin",
        config_path=config_path,
        live=live,
        max_ticks=64,
    )
