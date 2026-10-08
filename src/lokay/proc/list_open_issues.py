"""List open catalog issues from GitHub. Two small functions: facts, then envelope."""

from __future__ import annotations

import argparse
import json

from lokay.gh_rate import survey_list_cap
from lokay.proc._common import load_cfg, runner
from lokay.proc.scoped_active_repos import scoped_active_repos
from lokay.source import load_tasks


def _off_goal_parked(path) -> set[tuple[str, int]]:
    """Issues parked in lokay state: latest OFF_GOAL_PARK_AFTER issue_to_pr runs all off_goal."""
    from lokay.proc.check_executor_queue import OFF_GOAL_PARK_AFTER

    streaks: dict[tuple[str, int], int] = {}
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except OSError:
        return set()
    for line in lines:
        if '"issue_to_pr"' not in line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("kind") != "issue_to_pr" or not isinstance(event.get("issue"), int):
            continue
        key = (str(event.get("repo")), event["issue"])
        off_goal = event.get("delivered") is not True and '"reason": "off_goal"' in str(event.get("steps"))
        streaks[key] = streaks.get(key, 0) + 1 if off_goal else 0
    return {key for key, n in streaks.items() if n >= OFF_GOAL_PARK_AFTER}


def facts(*, config_path: str | None, live: bool) -> dict:
    """Live GitHub open-issue rows. No skip/route — overflow is a fact."""
    cfg = load_cfg(argparse.Namespace(config=config_path))
    git = runner()
    rows: list[dict] = []
    overflow = False
    cap = survey_list_cap()
    # Parked issues leave the listing so no picker re-selects them (no labels).
    parked = _off_goal_parked(cfg.state_path) if live else set()
    for repo in scoped_active_repos(cfg):
        listed = load_tasks(
            repo, runner=git, config=cfg, live=live, on_cap="keep"
        ).list_open()
        if live and len(listed) >= cap:
            overflow = True
        # Source APIs may return newest first. Keep repo priority, but do not
        # start a newer integration ticket ahead of its older foundations.
        for task in sorted(listed, key=lambda task: int(task.number)):
            if (repo.name, int(task.number)) in parked:
                continue
            rows.append(
                {
                    "repo": repo.name,
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
