"""Invoke the authored catalog PR-closeout Fala."""

from lokay.graph_run import run_path


def run(*, pass_dir: str, config_path: str | None, live: bool) -> dict:
    return run_path(
        path_id="closeout_prs",
        repo="local/pr-closeout",
        config_path=config_path,
        live=live,
        max_ticks=16,
        extra_inputs={"pass_dir": pass_dir},
    )
