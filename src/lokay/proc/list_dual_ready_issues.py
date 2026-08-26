"""List open work:ready issues for one repository (dual-ready probe)."""

import argparse

from lokay.config import RepoConfig
from lokay.gh_issues import WORK_READY_LABEL, is_github_rate_limit_error, list_labeled_issues
from lokay.proc._common import load_cfg, runner


def fetch(selected: dict, *, config_path: str | None, live: bool) -> dict:
    cfg = load_cfg(argparse.Namespace(config=config_path, live=live))
    name = str(selected["repo"])
    repo = next((row for row in cfg.active_repos() if row.name == name), None)
    if repo is None:
        repo = RepoConfig(name=name, clone_path=cfg.worktrees_root / "unused")
    label = str((selected.get("labels") or [WORK_READY_LABEL])[0] or WORK_READY_LABEL)
    try:
        issues = list_labeled_issues(
            runner(cfg), cfg, repo, label=label, live=live
        )
    except RuntimeError as exc:
        if not is_github_rate_limit_error(exc):
            raise
        return {
            **selected,
            "ok": True,
            "route": "failed",
            "error": str(exc),
            "issues": [],
        }
    return {
        **selected,
        "ok": True,
        "route": "listed",
        "issues": [
            {
                "repo": name,
                "number": int(row.number),
                "labels": list(row.labels),
                "state": row.state,
            }
            for row in issues
        ],
    }
