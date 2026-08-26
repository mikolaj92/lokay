"""Invoke the authored pass-planning Fala."""

from lokay.graph_run import run_path


def run(*, pass_dir: str) -> dict:
    return run_path(
        path_id="plan_pass",
        repo="local/pass-plan",
        live=False,
        max_ticks=16,
        extra_inputs={"pass_dir": pass_dir},
    )
