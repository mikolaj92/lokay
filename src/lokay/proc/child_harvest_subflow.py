"""Invoke one authored detached-child harvest subflow."""

from pathlib import Path

from lokay.graph_run import run_path
from lokay.preflight import trusted_fala_manifest


def run(config: dict, scope: dict, ledger: dict) -> dict:
    return run_path(
        path_id="child_harvest",
        repo="__child_harvest__",
        config_path=config.get("config_path") or None,
        live=bool(config.get("live")),
        package_path=str(trusted_fala_manifest()),
        db_path=Path(config["state_path"]).parent / "fala" / "child-harvest",
        max_ticks=128,
        extra_inputs={
            "harvest_config": config,
            "harvest_scope": scope,
            "harvest_ledger": ledger,
        },
    )
