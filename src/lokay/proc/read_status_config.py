"""Read one status configuration into a bounded public fact."""

import argparse

from lokay.proc._common import load_cfg


def read(*, config_path: str | None, preflight: bool, full: bool) -> dict:
    cfg = load_cfg(argparse.Namespace(config=config_path))
    repos = [
        {"name": r.name, "enabled": r.enabled, "clone_path": str(r.clone_path)}
        for r in cfg.repos
    ]
    return {
        "ok": True,
        "config": str(cfg.config_path),
        "mode": cfg.mode,
        "executor_enabled": cfg.executor_enabled,
        "agent": cfg.agent,
        "incident_repo": cfg.incident_repo,
        "merge_enabled": cfg.merge_enabled,
        "require_checks": cfg.require_checks,
        "require_llm_review": cfg.require_llm_review,
        "max_issue_to_pr_per_pass": cfg.max_issue_to_pr_per_pass,
        "state_path": str(cfg.state_path),
        "repos": repos,
        "preflight_requested": preflight,
        "full": full,
    }
