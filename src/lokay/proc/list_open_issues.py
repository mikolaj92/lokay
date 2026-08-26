"""List open catalog issues from GitHub. Labels are not a gate."""

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
    for repo in cfg.active_repos():
        try:
            listed = list_ready_issues(
                git, cfg, repo, live=live, on_cap="keep"
            )
        except RuntimeError as exc:
            # Cap overflow is leftover skip. Other list failures stay errors.
            if "newest-first cap" not in str(exc):
                raise
            overflow = True
            continue
        if live and len(listed) >= survey_list_cap():
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
    if not rows:
        return {
            "ok": True,
            "route": "skip",
            "reason": "overflow" if overflow else "empty",
            "skipped": True,
            "issues": [],
            "count": 0,
        }
    return {
        "ok": True,
        "route": "listed",
        "issues": rows,
        "count": len(rows),
        "overflow": overflow,
    }
