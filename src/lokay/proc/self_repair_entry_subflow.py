"""Invoke authored self-repair entry Fala."""

from pathlib import Path

from lokay.graph_run import run_path
from lokay.preflight import trusted_fala_manifest


def run(*, config_path: str | None, preflight: dict) -> dict:
    return run_path(
        path_id="self_repair_entry",
        repo="__self_repair_entry__",
        config_path=config_path,
        live=True,
        package_path=str(trusted_fala_manifest()),
        db_path=Path.home() / ".lokay" / "fala" / "self-repair-entry",
        max_ticks=40,
        extra_inputs={"config_path": config_path or "", "preflight": preflight},
    )
