"""List open catalog issues from GitHub. Two small functions: facts, then envelope."""

from __future__ import annotations

import argparse

from lokay.gh_rate import survey_list_cap
from lokay.proc._common import load_cfg, runner
from lokay.github_tasks import issues_source


def facts(*, config_path: str | None, live: bool) -> dict:
    """Live GitHub open-issue rows. No skip/route — overflow is a fact."""
    cfg = load_cfg(argparse.Namespace(config=config_path))
    git = runner()
    rows: list[dict] = []
    overflow = False
    cap = survey_list_cap()
    for repo in cfg.active_repos():
        listed = issues_source(
            repo, runner=git, config=cfg, live=live, on_cap="keep"
        ).list_open()
        if live and len(listed) >= cap:
            overflow = True
        for task in listed:
            rows.append(
                {
                    "repo": task.target,
                    "issue": int(task.number),
                    "title": task.title,
                    "labels": list(task.labels or []),
                    "assignees": list(task.assignees or []),
                }
            )
    return {
        "issues": rows,
        "count": len(rows),
        "overflow": overflow,
        "assignee": str(getattr(cfg, "assignee", "") or "mikolaj92"),
    }


def run(*, config_path: str | None, live: bool) -> dict:
    return {"ok": True, **facts(config_path=config_path, live=live)}
