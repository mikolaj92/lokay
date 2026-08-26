"""Invoke the authored implementation-selection Fala."""

from lokay.graph_run import run_path


def run(*, pass_dir: str) -> dict:
    return run_path(
        path_id="select_implement",
        repo="local/implementation-selection",
        live=False,
        max_ticks=16,
        extra_inputs={"pass_dir": pass_dir},
    )
