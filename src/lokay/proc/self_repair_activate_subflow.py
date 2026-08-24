"""Invoke authored exact self-repair activation Fala."""

from lokay.graph_run import run_path


def run(*, config_path: str | None, live: bool, commit: str) -> dict:
    return run_path(
        path_id="self_repair_activate_execution",
        repo="mikolaj92/lokay",
        config_path=config_path,
        live=live,
        max_ticks=48,
        extra_inputs={
            "config_path": config_path or "",
            "live": live,
            "commit": commit,
            "repo": "mikolaj92/lokay",
        },
    )
