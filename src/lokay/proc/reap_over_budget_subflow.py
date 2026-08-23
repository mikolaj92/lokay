"""Invoke the authored over-budget detached-worker Fala."""

from lokay.graph_run import run_path


def run(
    *, budget_s: int, pass_dir: str | None, config_path: str | None, live: bool
) -> dict:
    return run_path(
        path_id="reap_over_budget",
        repo="local/over-budget",
        config_path=config_path,
        live=live,
        max_ticks=1024,
        extra_inputs={"pass_dir": pass_dir or "", "budget_s": budget_s},
    )
