"""One job: preflight + open a factory-pass workspace (budgets, stuck, planned)."""

from __future__ import annotations

import argparse
import os
from typing import Any

from lokay.envelope import emit_exit, err, ok
from lokay.passkit import io as pass_io
from lokay.passkit.hot import load_last_pass_by_repo, pick_survey_repos
from lokay.proc._common import add_config_live, load_cfg
from lokay.preflight import health_lease_status, run_preflight
from lokay.child_harvest import harvest_fail_closed_children
from lokay.stuck import load_stuck, save_stuck, stuck_path_for
from lokay.mill_scope import mill_repo, scoped_repos


MINI_MILL_REPO = mill_repo()


def _offline() -> bool:
    return os.environ.get("LOKAY_OFFLINE", "").strip() in {"1", "true", "yes"}


def run_factory_begin(*, config_path: str | None, live: bool) -> dict[str, Any]:
    # Parent daemon/Fala already passed preflight and issued a process-tree lease.
    # Re-running here would mistake the parent's singleton lock for contention.
    lease_ok, lease_reason = health_lease_status()
    if live and os.environ.get("LOKAY_HEALTH_LEASE"):
        # A delegated capability must validate as-is. Restore only a missing
        # file for the same token — never mint a replacement for expired/mismatch.
        if not lease_ok and (
            str(lease_reason).startswith("lease_unavailable_FileNotFound")
            or str(lease_reason).startswith("lease_unavailable_ProcessLookup")
            or str(lease_reason) == "lock_not_held"
        ):
            from lokay.preflight import issue_health_lease

            try:
                issue_health_lease()
            except RuntimeError:
                pass
            lease_ok, lease_reason = health_lease_status()
        preflight = (
            {"ok": True, "lease": True}
            if lease_ok
            else {"ok": False, "lease": False, "lease_reason": lease_reason}
        )
    else:
        preflight = run_preflight(config_path, remediate=True) if live else {"ok": True}
    if not preflight.get("ok"):
        return err(
            "preflight failed; product workflow blocked",
            health="preflight_failed",
            preflight=preflight,
            live=live,
            executed=False,
            progress=0,
            idle=False,
            actions=[],
            planned=[],
        )

    cfg = load_cfg(argparse.Namespace(config=config_path))
    if live and cfg.mode != "live":
        return err("refusing --live while config mode is not live")

    configured_repos = [r.name for r in cfg.active_repos()]
    # The mini mill is Lokay's own delivery lane. Product repositories may
    # remain in the shared catalog, but must never enter its pass workspace:
    # every later survey atom treats begin.repos as permission to call GitHub.
    repos, _ = scoped_repos(configured_repos, mill=MINI_MILL_REPO)

    pipeline = [
        "survey: list-prs + list-inbox + list-issues (hot repos + rotated cold)",
        "per-repo PR-first: conflict close / repair / merge open AI PRs",
        "inbox triage + deterministic intake (skip repos with actionable open AI PRs)",
        "occupancy then reap leftover worktrees then issue_to_pr up to K across clean (not occupied) repos",
        "on failure: stuck ledger → ai:blocked",
    ]
    planned = [
        {
            "kind": "tick",
            "status": "mutating" if live else "survey",
            "repos": repos,
            "agent": cfg.agent,
            "pipeline": pipeline,
        }
    ]

    if _offline():
        return ok(
            mode=cfg.mode,
            live=live,
            executed=False,
            planned=planned,
            actions=[],
            idle=False,
            remaining={"note": "offline"},
            health="offline",
            progress=0,
            offline=True,
        )

    stuck_path = stuck_path_for(cfg.state_path)
    stuck = load_stuck(stuck_path)
    harvest_fail_closed_children(stuck, state_path=cfg.state_path)
    save_stuck(stuck_path, stuck)
    pass_dir = pass_io.make_pass_dir(cfg.state_path)
    pass_io.prune_pass_dirs(cfg.state_path, keep_path=pass_dir)
    survey_repos = pick_survey_repos(
        repos,
        load_last_pass_by_repo(cfg.state_path),
        salt=str(pass_dir),
        extra_cold=max(2, int(cfg.max_issue_to_pr_per_pass)),
    )
    begin = {
        "pass_dir": str(pass_dir),
        "config_path": str(cfg.config_path) if cfg.config_path else config_path,
        "live": bool(live),
        "mode": cfg.mode,
        "repos": repos,
        "survey_repos": survey_repos,
        "stuck_path": str(stuck_path),
        "stuck": stuck,
        "planned": planned,
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
        "state_path": str(cfg.state_path),
    }
    pass_io.write_json(pass_io.begin_path(pass_dir), begin)
    # Mutable working ledger shared by later atoms.
    pass_io.write_json(
        pass_io.working_path(pass_dir),
        {
            "actions": [],
            "progress": 0,
            "blocked_this_pass": 0,
            "pending_checks": 0,
            "no_checks_blocked": 0,
            "merge_conflicts": 0,
            "needs_repair": 0,
            "mergeable_green": 0,
            "merge_disabled": 0,
            "review_limbo": 0,
            "remaining_inbox": 0,
            "remaining_ready": 0,
            "remaining_ready_with_pr": 0,
            "remaining_prs": 0,
            "actionable_prs": 0,
            "manual_prs": 0,
            "survey_errors": 0,
            "intake_skip_reason": None,
            "issue_to_pr_started": 0,
            "merged_this_pass": [],
            "occupied_repos": [],
            "live_issue_to_pr_repos": [],
            "prs_by_repo": {},
            "inbox_by_repo": {},
            "ready_by_repo": {},
            "pr_survey_failed": [],
            "inbox_survey_failed": [],
            "ready_survey_failed": [],
            "stuck": stuck,
        },
    )
    return ok(
        pass_dir=str(pass_dir),
        live=live,
        mode=cfg.mode,
        planned=planned,
        stuck_path=str(stuck_path),
        offline=False,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-factory-begin")
    add_config_live(parser)
    args = parser.parse_args(argv)
    return emit_exit(run_factory_begin(config_path=args.config, live=bool(args.live)))


if __name__ == "__main__":
    raise SystemExit(main())
