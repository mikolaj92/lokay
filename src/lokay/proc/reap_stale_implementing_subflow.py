"""Invoke the authored stale-stage recovery Fala."""

from lokay.graph_run import run_path


def run(*, pass_dir: str | None, config_path: str | None, live: bool) -> dict:
    return run_path(
        path_id="reap_stale_implementing",
        repo="local/stale-implementing",
        config_path=config_path,
        live=live,
        max_ticks=1024,
        extra_inputs={"pass_dir": pass_dir or ""},
    )
