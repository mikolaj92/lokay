"""Re-read one issue immediately before its stage transition."""

import argparse

from lokay.gh_issues import get_issue
from lokay.proc._common import load_cfg, runner


def read(prepared: dict, *, config_path: str | None) -> dict:
    cfg = load_cfg(argparse.Namespace(config=config_path, live=prepared.get("live")))
    try:
        issue = get_issue(
            runner(),
            cfg,
            prepared["repo"],
            int(prepared["issue"]),
            live=bool(prepared.get("live")),
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": True,
            "route": "terminal",
            "reason": "issue_probe_failed",
            "error": str(exc),
            "issue_state": "UNKNOWN",
        }
    return {
        "ok": True,
        "route": "classify",
        "issue_state": "MISSING" if issue is None else str(issue.state or "").upper(),
    }
