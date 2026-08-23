"""List one active ledger label for one selected repository."""

import argparse
from lokay.proc._common import load_cfg, runner
from lokay.gh_issues import is_github_rate_limit_error, list_labeled_issues


def fetch(selected: dict, *, config_path: str | None, live: bool, label: str) -> dict:
    cfg = load_cfg(argparse.Namespace(config=config_path))
    repo = next(x for x in cfg.active_repos() if x.name == selected["repo"])
    try:
        issues = list_labeled_issues(runner(cfg), cfg, repo, label=label, live=live)
    except RuntimeError as exc:
        if is_github_rate_limit_error(exc):
            return {
                "ok": True,
                "route": "failed",
                "repo": repo.name,
                "label": label,
                "error": str(exc),
                "issues": [],
            }
        raise
    return {
        "ok": True,
        "route": "listed",
        "repo": repo.name,
        "label": label,
        "issues": [
            {"repo": repo.name, "issue": int(x.number), "label": label} for x in issues
        ],
    }
