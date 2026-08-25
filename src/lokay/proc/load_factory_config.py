"""Load one factory configuration snapshot."""

import argparse
from lokay.proc._common import load_cfg


def load(*, config_path: str | None, live: bool) -> dict:
    cfg = load_cfg(argparse.Namespace(config=config_path, live=live))
    repos = [str(x.name) for x in cfg.active_repos()]
    return {
        "ok": True,
        "mode": cfg.mode,
        "live": live,
        "config_path": str(cfg.config_path) if cfg.config_path else config_path,
        "state_path": str(cfg.state_path),
        "repos": repos,
        "agent": cfg.agent,
        "triage_budget": max(0, int(cfg.max_triage_per_tick)) if live else 0,
        "issue_budget": max(0, int(cfg.max_issue_to_pr_per_pass)) if live else 0,
        "repair_budget": max(0, int(cfg.max_repairs_per_tick)) if live else 0,
        "max_fail": max(1, int(cfg.max_failures_before_block)),
        "max_issue_to_pr_per_pass": int(cfg.max_issue_to_pr_per_pass),
        "executor_enabled": bool(cfg.executor_enabled),
        "merge_enabled": bool(cfg.merge_enabled),
        "require_checks": bool(cfg.require_checks),
        "require_llm_review": bool(cfg.require_llm_review),
        "ready_label": cfg.ready_label,
        "blocked_label": cfg.blocked_label,
        "branch_prefix": cfg.branch_prefix,
        "incident_repo": str(cfg.incident_repo or "").strip(),
    }
