"""Recheck the physical open + ready-label facts for one selected issue."""

from lokay.gh_issues import get_issue
from lokay.proc._common import load_cfg, runner
import argparse


def verify(candidate: dict, *, config_path: str | None) -> dict:
    cfg = load_cfg(argparse.Namespace(config=config_path))
    try:
        issue = get_issue(
            runner(), cfg, str(candidate["repo"]), int(candidate["issue"]), live=False
        )
    except Exception as exc:
        return {
            "ok": True,
            "route": "stale",
            "reason": "unknown",
            "error": str(exc),
            **candidate,
        }
    ready = (
        issue is not None
        and (issue.state or "OPEN").upper() == "OPEN"
        and cfg.ready_label in (issue.labels or [])
    )
    return {
        "ok": True,
        "route": "ready" if ready else "stale",
        "physical_issue": issue.to_dict() if issue else None,
        **candidate,
    }
