"""Invoke the authored localization-execution Fala."""

from lokay.graph_run import run_path


def run(*, config_path: str | None, live: bool, extra_inputs: dict) -> dict:
    return run_path(
        path_id="localize_execution",
        repo=str(extra_inputs.get("repo") or "local/localize"),
        config_path=config_path,
        live=live,
        max_ticks=64,
        extra_inputs=extra_inputs,
    )
