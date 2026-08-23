"""Invoke the authored issue-to-PR delivery Fala after the open-issue gate."""

from __future__ import annotations
from lokay.graph_run import run_path


def invoke(
    *,
    config_path: str | None,
    repo: str,
    issue: int,
    live: bool,
    incident_fingerprint: str = "",
) -> dict:
    return run_path(
        path_id="issue_to_pr_delivery",
        repo=repo,
        issue=issue,
        config_path=config_path,
        live=live,
        extra_inputs={
            "incident_fingerprint": incident_fingerprint,
            "keep_issue_open": bool(incident_fingerprint),
        },
    )
