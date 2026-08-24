"""Invoke authored read-only status snapshot Fala."""

import os

from lokay.graph_run import run_path

_REQUIRED = (
    "LOKAY_PROCESS_HEAD",
    "LOKAY_HOST_FF_FETCHED",
    "LOKAY_HEALTH_LEASE",
    "LOKAY_HEALTH_LEASE_PATH",
    "LOKAY_DISABLE_HEALTH_LEASE_ISSUE",
)


def run(
    *, config_path: str | None, preflight: bool = False, full: bool = False
) -> dict:
    missing = [k for k in _REQUIRED if k not in os.environ]
    try:
        for key in missing:
            os.environ[key] = ""
        return run_path(
            path_id="status_snapshot",
            repo="local/status",
            config_path=config_path,
            live=False,
            max_ticks=48,
            extra_inputs={
                "config_path": config_path or "",
                "preflight": preflight,
                "full": full,
                "repo": "local/status",
            },
        )
    finally:
        for key in missing:
            os.environ.pop(key, None)
