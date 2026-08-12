"""Composer: DoD readiness + remaining work (read-only survey).

Reports whether config can mill live and what work remains. Never mutates.
Exit ok=false when work remains or mill is not configured for live progress.

Default path surveys all repos. Use --local / --skip-survey for a cheap
readiness/config/lease/preflight summary without the multi-repo gh survey.
One command surfaces: mill_ready, merge_enabled, K limit, health, per-repo
actionable PRs / ready / inbox, and a compact human_residuals count.
"""

from __future__ import annotations

import argparse
import os
from typing import Any

from lokay.compose.human_mailbox import compose_human_mailbox
from lokay.compose.tick import compose_tick
from lokay.envelope import emit_exit, ok
from lokay.graph_run import describe_package
from lokay.pass_receipt import read_pass_receipt
from lokay.preflight import health_lease_status, run_preflight
from lokay.proc._common import add_config, load_cfg


def _offline() -> bool:
    return os.environ.get("LOKAY_OFFLINE", "").strip() in {"1", "true", "yes"}


def _human_residuals_compact(config_path: str | None) -> dict[str, Any]:
    """Survey residual mailbox; never a mill brake."""
    if _offline():
        return {
            "count": 0,
            "ok": True,
            "items": [],
            "note": "offline — human mailbox survey skipped",
            "mill_blocked": False,
        }
    try:
        mailbox = compose_human_mailbox(config_path=config_path, live=True)
    except Exception as exc:  # noqa: BLE001
        return {
            "count": 0,
            "ok": False,
            "error": str(exc),
            "items": [],
            "note": "human mailbox survey failed — mill is not blocked",
            "mill_blocked": False,
        }
    items = list(mailbox.get("items") or [])
    # Compact: keep short rows for the operator glance; full list via --human.
    compact_items = [
        {
            "kind": it.get("kind"),
            "repo": it.get("repo"),
            "number": it.get("number"),
            "label": it.get("label"),
            "title": it.get("title"),
        }
        for it in items
    ]
    return {
        "count": int(mailbox.get("count") or len(items)),
        "ok": bool(mailbox.get("ok")),
        "items": compact_items,
        "errors": list(mailbox.get("errors") or []),
        "mill_blocked": False,
        "note": mailbox.get("note")
        or "Human queue is exception reporting only — use --human for mailbox detail",
    }


def _autonomy_fields(
    cfg: Any,
    *,
    health: Any,
    remaining: Any,
    human_residuals: dict[str, Any] | None,
    last_pass: dict[str, Any] | None,
) -> dict[str, Any]:
    by_repo: list[dict[str, Any]] = []
    if isinstance(remaining, dict):
        raw = remaining.get("by_repo")
        if isinstance(raw, list):
            by_repo = list(raw)
    return {
        "merge_enabled": bool(cfg.merge_enabled),
        "max_issue_to_pr_per_pass": int(cfg.max_issue_to_pr_per_pass),
        "k": int(cfg.max_issue_to_pr_per_pass),
        "health": health,
        "by_repo": by_repo,
        "human_residuals": human_residuals,
        "last_pass": last_pass,
    }


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
        "LOKAY_REQUIRE_LLM_REVIEW=1 "
        "uv run lokay-mill --config config.yaml --live"
    )
    last_pass = read_pass_receipt(state_path=cfg.state_path)

    if not survey:
        preflight_summary: dict[str, Any] | None = None
        if preflight_check:
            preflight_summary = run_preflight(
                config_path, remediate=False, issue_lease=False
            )
        # Local: surface last receipt health so operators need not re-survey.
        health = (last_pass or {}).get("health") or "local"
        remaining_local: dict[str, Any] = {"note": "survey_skipped"}
        if isinstance(last_pass, dict) and isinstance(last_pass.get("remaining"), dict):
            remaining_local = {
                "note": "survey_skipped",
                "from_last_pass": last_pass.get("remaining"),
            }
        human_local = None
        if isinstance(last_pass, dict) and isinstance(last_pass.get("human_residuals"), dict):
            human_local = last_pass.get("human_residuals")
        autonomy = _autonomy_fields(
            cfg,
            health=health,
            remaining=(last_pass or {}).get("remaining") if last_pass else remaining_local,
            human_residuals=human_local,
            last_pass=last_pass,
        )
        payload = ok(
            kind="status",
            config=str(cfg.config_path),
            mode=cfg.mode,
            executor_enabled=cfg.executor_enabled,
            agent=cfg.agent,
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
            idle=None if last_pass is None else last_pass.get("idle"),
            remaining=remaining_local,
            survey_ok=None,
            work_units=None,
            lease_ok=lease_ok,
            lease_reason=lease_reason,
            preflight=preflight_summary,
            live_env_hint=live_env_hint if not mill_ready else None,
            note=(
                "local status (survey skipped) — health/by_repo from last_pass when present; "
                "use --full for live remaining work"
            ),
            **autonomy,
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

    human_residuals = _human_residuals_compact(config_path)
    # Refresh receipt with human residual count so --local sees it next time.
    last_pass = read_pass_receipt(state_path=cfg.state_path)
    if isinstance(last_pass, dict):
        last_pass = {
            **last_pass,
            "human_residuals": {
                "count": int(human_residuals.get("count") or 0),
                "note": human_residuals.get("note"),
            },
        }
        try:
            from lokay.pass_receipt import write_pass_receipt

            write_pass_receipt(last_pass, state_path=cfg.state_path)
        except OSError:
            pass

    autonomy = _autonomy_fields(
        cfg,
        health=survey_result.get("health"),
        remaining=remaining,
        human_residuals=human_residuals,
        last_pass=last_pass,
    )
    payload = ok(
        kind="status",
        config=str(cfg.config_path),
        mode=cfg.mode,
        executor_enabled=cfg.executor_enabled,
        agent=cfg.agent,
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
        remaining=remaining,
        survey_ok=survey_result.get("ok"),
        work_units=work,
        lease_ok=lease_ok,
        lease_reason=lease_reason,
        live_env_hint=live_env_hint if not mill_ready else None,
        pass_receipt_path=survey_result.get("pass_receipt_path"),
        **autonomy,
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
