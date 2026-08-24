"""Invoke authored one-PR publication Fala."""

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
    *,
    config_path: str | None,
    live: bool,
    repo: str,
    issue: int | None,
    title: str,
    body: str,
    head: str,
    base: str,
) -> dict:
    missing = [k for k in _REQUIRED if k not in os.environ]
    try:
        for key in missing:
            os.environ[key] = ""
        return run_path(
            path_id="pr_create_execution",
            repo=repo,
            issue=issue,
            config_path=config_path,
            live=live,
            max_ticks=32,
            extra_inputs={
                "config_path": config_path or "",
                "live": live,
                "repo": repo,
                "issue": issue,
                "title": title,
                "body": body,
                "head": head,
                "base": base,
            },
        )
    finally:
        for key in missing:
            os.environ.pop(key, None)
