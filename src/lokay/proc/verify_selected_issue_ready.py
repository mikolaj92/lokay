"""Recheck that one selected issue is still open work, not a human stop."""

from lokay.gh_issues import get_issue
from lokay.proc._common import load_cfg, runner
from lokay.triage import is_open_work_issue
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
    ready = issue is not None and is_open_work_issue(
        issue.labels or [],
        state=issue.state or "OPEN",
        blocked_label=cfg.blocked_label,
        needs_feedback_label=cfg.needs_feedback_label,
    )
    return {
        "ok": True,
        "route": "ready" if ready else "stale",
        "physical_issue": issue.to_dict() if issue else None,
        **candidate,
    }
