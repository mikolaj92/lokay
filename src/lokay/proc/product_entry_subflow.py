"""Invoke authored direct-product entry routing."""

from pathlib import Path

from lokay.graph_run import run_path
from lokay.preflight import trusted_fala_manifest


def run(
    *, config_path: str | None, live: bool, max_passes: int, preflight: dict
) -> dict:
    return run_path(
        path_id="product_entry",
        repo="__product_entry__",
        config_path=config_path,
        live=live,
        package_path=str(trusted_fala_manifest()),
        db_path=Path.home() / ".lokay" / "fala" / "product-entry",
        max_ticks=24,
        extra_inputs={
            "entry_config_path": config_path or "",
            "entry_live": live,
            "entry_max_passes": max(1, int(max_passes)),
            "entry_preflight": preflight,
        },
    )
