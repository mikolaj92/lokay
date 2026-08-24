"""List CLOSED issues for one repository and one ready label."""

import argparse
from lokay.proc._common import load_cfg, runner
from lokay.proc.closeout import closed_ready_numbers
from lokay.gh_issues import is_github_rate_limit_error


def fetch(selected: dict, *, config_path: str | None, live: bool) -> dict:
    cfg = load_cfg(argparse.Namespace(config=config_path, live=live))
    try:
        numbers = closed_ready_numbers(
            runner(cfg), selected["repo"], selected["label"], live=live
        )
    except RuntimeError as exc:
        if not is_github_rate_limit_error(exc):
            raise
        return {
            **selected,
            "ok": True,
            "route": "failed",
            "error": str(exc),
            "numbers": [],
        }
    return {**selected, "ok": True, "route": "listed", "numbers": numbers}
