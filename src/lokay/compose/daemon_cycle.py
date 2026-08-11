"""Fala-owned daemon cycle: product mill, stall quorum, and recovery conduction."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lokay.graph_run import run_path
from lokay.preflight import trusted_fala_manifest


def compose_daemon_cycle(
    *, config_path: str, max_passes: int = 8
) -> dict[str, Any]:
    return run_path(
        path_id="daemon_cycle",
        repo="__lokay_daemon__",
        config_path=config_path,
        live=True,
        package_path=str(trusted_fala_manifest()),
        db_path=Path.home() / ".lokay" / "fala" / "daemon-cycle",
        extra_inputs={"max_passes": max(1, int(max_passes))},
    )
