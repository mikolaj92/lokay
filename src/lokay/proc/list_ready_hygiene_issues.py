"""List issues carrying the configured ready label in one repository."""

import argparse
from lokay.gh_issues import is_github_rate_limit_error, list_labeled_issues
from lokay.proc._common import load_cfg, runner


def fetch(selected: dict, *, config_path: str | None, live: bool) -> dict:
    cfg = load_cfg(argparse.Namespace(config=config_path, live=live))
    try:
        issues = list_labeled_issues(
            runner(cfg),
            cfg,
            next(x for x in cfg.active_repos() if x.name == selected["repo"]),
            label=selected["ready_label"],
            live=live,
        )
    except RuntimeError as exc:
        if is_github_rate_limit_error(exc):
            return {
                **selected,
                "ok": True,
                "route": "failed",
                "error": str(exc),
                "issues": [],
            }
        raise
    return {
        **selected,
        "ok": True,
        "route": "listed",
        "issues": [
            {
                "repo": selected["repo"],
                "number": int(x.number),
                "labels": list(x.labels),
            }
            for x in issues
        ],
    }
