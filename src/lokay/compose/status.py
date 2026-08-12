"""Composer: DoD readiness + remaining work (read-only survey).

Reports whether config can mill live and what work remains. Never mutates.
Exit ok=false when work remains or mill is not configured for live progress.

Default path surveys all repos. Use --local / --skip-survey for a cheap
readiness/config/lease/preflight summary without the multi-repo gh survey.
"""

from __future__ import annotations

import argparse
from typing import Any

from lokay.compose.human_mailbox import compose_human_mailbox
from lokay.compose.tick import compose_tick
from lokay.envelope import emit_exit, ok
from lokay.graph_run import describe_package
from lokay.preflight import health_lease_status, run_preflight
from lokay.proc._common import add_config, load_cfg


def compose_status(
    *,
    config_path: str | None,
    survey: bool = True,
    preflight_check: bool = False,
    human: bool = False,
) -> dict[str, Any]:
    if human:
        # Residual mailbox — never implies mill stuck / not-working.
        return compose_human_mailbox(config_path=config_path, live=True)
    cfg = load_cfg(argparse.Namespace(config=config_path))
    # Hard blockers: mill cannot act at all (not policy tradeoffs).
    blockers: list[str] = []
    if cfg.mode != "live":
        blockers.append("mode is not live (need mode: live)")
    if not cfg.executor_enabled:
        blockers.append("executor.enabled is false (agent never runs)")
    if not cfg.merge_enabled:
        blockers.append("merge.enabled is false (PRs cannot merge)")
    # require_checks is policy for no-CI PRs (counted as no_checks_blocked), not a mill_ready
    # hard stop — mill still triages inbox, implements ready, repairs failed CI, merges green.
    policy_notes: list[str] = []
    if cfg.require_checks:
        policy_notes.append(
            "merge.require_checks=true: no-CI PRs wait (no_checks_blocked); green CI still merges"
        )
    missing_clones = [
        f"{repo.name} → {repo.clone_path}"
        for repo in cfg.active_repos()
        if not repo.clone_path.exists()
    ]
    # Missing clones do not block mill_ready for triage-only progress;
    # they block full implement for those repos (reported separately).
    if missing_clones:
        policy_notes.append(
            f"{len(missing_clones)} missing clone(s) — implement blocked there; triage still runs"
        )

    graphs = []
    try:
        graphs = [p["id"] for p in describe_package().get("paths") or []]
    except Exception:
        graphs = []

    mill_ready = not blockers
    lease_ok, lease_reason = health_lease_status(
        lock_path=cfg.state_path.parent / "mill.lock"
    )
    live_env_hint = (
        "LOKAY_MODE=live LOKAY_EXECUTOR_ENABLED=1 "
        "LOKAY_MERGE_ENABLED=1 LOKAY_REQUIRE_CHECKS=1 "
        "uv run lokay-mill --config config.yaml --live"
    )

    if not survey:
        preflight_summary: dict[str, Any] | None = None
        if preflight_check:
            preflight_summary = run_preflight(
                config_path, remediate=False, issue_lease=False
            )
        payload = ok(
            kind="status",
            config=str(cfg.config_path),
            mode=cfg.mode,
            executor_enabled=cfg.executor_enabled,
            agent=cfg.agent,
            merge_enabled=cfg.merge_enabled,
            require_checks=cfg.require_checks,
            incident_repo=cfg.incident_repo,
            repos=[r.name for r in cfg.active_repos()],
            repos_disabled=[r.name for r in cfg.repos if not r.enabled],
            repos_total=len(cfg.repos),
            missing_clones=missing_clones,
            graphs=graphs,
            mill_ready=mill_ready,
            blockers=blockers,
            policy_notes=policy_notes,
            survey=False,
            idle=None,
            health="local",
            remaining={"note": "survey_skipped"},
            survey_ok=None,
            work_units=None,
            lease_ok=lease_ok,
            lease_reason=lease_reason,
            preflight=preflight_summary,
            live_env_hint=live_env_hint if not mill_ready else None,
            note="local status (survey skipped) — use --full for remaining work",
        )
        if not mill_ready:
            payload["ok"] = False
            payload["error"] = "not working: mill is not live-ready"
        return payload

    survey_result = compose_tick(config_path=config_path, live=False)
    remaining = survey_result.get("remaining") or {}
    idle = bool(survey_result.get("idle"))
    # Production signal: either truly idle, or mill is ready and can act.
    # Fail when work remains while mill cannot act (the factory is NOT WORKING).
    work = 0
    survey_errors = 0
    if isinstance(remaining, dict) and "note" not in remaining:
        survey_errors = int(remaining.get("survey_errors") or 0)
        work = (
            int(remaining.get("inbox") or 0)
            + int(remaining.get("ready") or 0)
            + int(remaining.get("open_ai_prs") or 0)
            + survey_errors  # unknown work is still work — refuse green noop
        )

    payload = ok(
        kind="status",
        config=str(cfg.config_path),
        mode=cfg.mode,
        executor_enabled=cfg.executor_enabled,
        agent=cfg.agent,
        merge_enabled=cfg.merge_enabled,
        require_checks=cfg.require_checks,
        incident_repo=cfg.incident_repo,
        repos=[r.name for r in cfg.active_repos()],
        repos_disabled=[r.name for r in cfg.repos if not r.enabled],
        repos_total=len(cfg.repos),
        missing_clones=missing_clones,
        graphs=graphs,
        mill_ready=mill_ready,
        blockers=blockers,
        policy_notes=policy_notes,
        survey=True,
        idle=idle,
        health=survey_result.get("health"),
        remaining=remaining,
        survey_ok=survey_result.get("ok"),
        work_units=work,
        lease_ok=lease_ok,
        lease_reason=lease_reason,
        live_env_hint=live_env_hint if not mill_ready else None,
    )
    if not idle and not mill_ready:
        payload["ok"] = False
        payload["error"] = "not working: work remains but mill is not live-ready"
    elif survey_errors > 0:
        payload["ok"] = False
        payload["error"] = "not working: survey atom failures (refuse false idle)"
        payload["note"] = "survey_errors > 0 — fix gh/network before trusting idle"
    elif not idle and mill_ready:
        # Configured to mill but work still there — status reports busy (ok true
        # for "status succeeded"; use health/work_units for operators).
        payload["note"] = "mill_ready with remaining work — run lokay-mill --live"
    elif idle and mill_ready:
        payload["note"] = "idle and mill_ready"
    elif idle and not mill_ready:
        payload["note"] = "idle now but mill not live-ready for future work"
    return payload


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-status")
    add_config(p)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "--local",
        "--skip-survey",
        action="store_true",
        dest="local",
        help="cheap readiness/config/lease summary (skip multi-repo survey)",
    )
    mode.add_argument(
        "--full",
        action="store_true",
        help="full multi-repo remaining-work survey (default)",
    )
    mode.add_argument(
        "--human",
        action="store_true",
        help="list residual human mailbox items (needs-feedback / needs-review); not a mill brake",
    )
    p.add_argument(
        "--preflight",
        action="store_true",
        help="with --local, also run host preflight checks (no lease issue)",
    )
    args = p.parse_args(argv)
    if args.human:
        return emit_exit(compose_status(config_path=args.config, human=True))
    survey = not bool(args.local)
    return emit_exit(
        compose_status(
            config_path=args.config,
            survey=survey,
            preflight_check=bool(args.preflight and args.local),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
