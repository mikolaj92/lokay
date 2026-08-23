"""Invoke the authored self-repair preparation Fala."""

from lokay.graph_run import run_path


def run(*, fingerprint: str, config_path: str | None, live: bool) -> dict:
    return run_path(
        path_id="self_repair_prepare",
        repo="mikolaj92/lokay",
        config_path=config_path,
        live=live,
        max_ticks=128,
        extra_inputs={"fingerprint": fingerprint},
    )
