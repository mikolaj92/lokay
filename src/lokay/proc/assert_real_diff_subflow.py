"""Invoke the authored physical real-diff assertion Fala."""

import os

from lokay.graph_run import run_path

_REQUIRED_ENV = (
    "LOKAY_PROCESS_HEAD",
    "LOKAY_HOST_FF_FETCHED",
    "LOKAY_HEALTH_LEASE",
    "LOKAY_HEALTH_LEASE_PATH",
    "LOKAY_DISABLE_HEALTH_LEASE_ISSUE",
)


def run(
    *, worktree: str, base: str = "origin/main", issue_body: str = "", repo: str = ""
) -> dict:
    missing = [key for key in _REQUIRED_ENV if key not in os.environ]
    try:
        for key in missing:
            os.environ[key] = ""
        return run_path(
            path_id="assert_real_diff_execution",
            repo=repo or "local/assert-real-diff",
            config_path=None,
            live=False,
            max_ticks=48,
            extra_inputs={
                "worktree": worktree,
                "base": base,
                "issue_body": issue_body,
                "repo": repo,
            },
        )
    finally:
        for key in missing:
            os.environ.pop(key, None)
