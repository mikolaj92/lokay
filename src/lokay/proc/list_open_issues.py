"""List open catalog issues from GitHub. Labels are not a gate."""

from __future__ import annotations

import argparse

from lokay.gh_issues import list_ready_issues
from lokay.proc._common import load_cfg, runner


def run(*, config_path: str | None, live: bool) -> dict:
    cfg = load_cfg(argparse.Namespace(config=config_path))
    git = runner()
    rows: list[dict] = []
    for repo in cfg.active_repos():
        for issue in list_ready_issues(git, cfg, repo, live=live):
            rows.append(
                {
                    "repo": issue.repo,
                    "issue": int(issue.number),
                    "title": issue.title,
                    "labels": list(issue.labels or []),
                }
            )
    return {"ok": True, "issues": rows, "count": len(rows)}
