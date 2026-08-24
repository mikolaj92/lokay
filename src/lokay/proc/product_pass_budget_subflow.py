"""Invoke the authored serial product-pass budget Fala."""

from lokay.graph_run import run_path


def run(*, config_path: str | None, live: bool, max_passes: int) -> dict:
    return run_path(
        path_id="product_pass_budget",
        repo="local/product-budget",
        config_path=config_path,
        live=live,
        max_ticks=128,
        extra_inputs={"max_passes": max_passes},
    )
