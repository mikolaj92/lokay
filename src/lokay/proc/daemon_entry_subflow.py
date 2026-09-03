"""Invoke authored daemon-entry routing after the physical lock/preflight capability."""

from lokay.fala_journal import wrapper_journal_dir
from lokay.graph_run import run_path
from lokay.preflight import trusted_fala_manifest


def run(*, config_path: str, max_passes: int, preflight: dict) -> dict:
    return run_path(
        path_id="daemon_entry",
        repo="__lokay_daemon_entry__",
        config_path=config_path,
        live=True,
        package_path=str(trusted_fala_manifest()),
        db_path=wrapper_journal_dir("daemon_entry"),
        max_ticks=24,
        extra_inputs={
            "config_path": config_path,
            "max_passes": max_passes,
            "preflight": preflight,
        },
    )
