"""Invoke the authored factory-begin Fala."""

from lokay.graph_run import run_path
from lokay.proc.factory_begin_receipt import begin_receipt


def run(*, config_path: str | None, live: bool) -> dict:
    return begin_receipt(
        run_path(
            path_id="factory_begin",
            repo="local/factory-begin",
            config_path=config_path,
            live=live,
            max_ticks=32,
            require_healthy=False,
        )
    )
