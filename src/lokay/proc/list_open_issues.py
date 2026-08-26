"""List open catalog issues from GitHub. One job: list facts."""

from __future__ import annotations

import argparse

from lokay.gh_issues import list_ready_issues
from lokay.gh_rate import survey_list_cap
from lokay.proc._common import load_cfg, runner


def run(*, config_path: str | None, live: bool) -> dict:
    cfg = load_cfg(argparse.Namespace(config=config_path))
    git = runner()
    rows: list[dict] = []
    overflow = False
    cap = survey_list_cap()
    for repo in cfg.active_repos():
        listed = list_ready_issues(git, cfg, repo, live=live, on_cap="keep")
        if live and len(listed) >= cap:
            overflow = True
        for issue in listed:
            rows.append(
                {
                    "repo": issue.repo,
                    "issue": int(issue.number),
                    "title": issue.title,
                    "labels": list(issue.labels or []),
                }
            )
    return {
        "ok": True,
        "issues": rows,
        "count": len(rows),
        "overflow": overflow,
    }
