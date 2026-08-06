"""Composer: DoD readiness + remaining work (read-only survey).

Reports whether config can mill live and what work remains. Never mutates.
Exit ok=false when work remains or mill is not configured for live progress.
"""

from __future__ import annotations

import argparse
from typing import Any

from lokay.compose.tick import compose_tick
from lokay.envelope import emit_exit, ok
from lokay.graph_run import describe_package
from lokay.proc._common import add_config, load_cfg


def compose_status(*, config_path: str | None) -> dict[str, Any]:
    cfg = load_cfg(argparse.Namespace(config=config_path))
    blockers: list[str] = []
    if cfg.mode != "live":
        blockers.append("mode is not live (need mode: live)")
    if not cfg.executor_enabled:
        blockers.append("executor.enabled is false (agent never runs)")
    if not cfg.merge_enabled:
        blockers.append("merge.enabled is false (PRs cannot merge)")
    if cfg.require_checks:
        blockers.append(
            "merge.require_checks is true (no-CI PRs blocked; set false for canary/no-CI)"
        )
    missing_clones = [
        f"{repo.name} → {repo.clone_path}"
        for repo in cfg.active_repos()
        if not repo.clone_path.exists()
    ]
    # Missing clones do not block mill_ready for triage-only progress;
    # they block full implement for those repos (reported separately).

    survey = compose_tick(config_path=config_path, live=False)
    remaining = survey.get("remaining") or {}
    graphs = []
    try:
        graphs = [p["id"] for p in describe_package().get("paths") or []]
    except Exception:
        graphs = []

    mill_ready = not blockers
    idle = bool(survey.get("idle"))
    # Production signal: either truly idle, or mill is ready and can act.
    # Fail when work remains while mill cannot act (the factory is NOT WORKING).
    work = 0
    if isinstance(remaining, dict) and "note" not in remaining:
        work = (
            int(remaining.get("inbox") or 0)
            + int(remaining.get("ready") or 0)
            + int(remaining.get("open_ai_prs") or 0)
        )

    live_env_hint = (
        "LOKAY_MODE=live LOKAY_EXECUTOR_ENABLED=1 LOKAY_AGENT=fake "
        "LOKAY_MERGE_ENABLED=1 LOKAY_REQUIRE_CHECKS=0 "
        "uv run lokay-mill --config config.yaml --live"
    )
    payload = ok(
        kind="status",
        config=str(cfg.config_path),
        mode=cfg.mode,
        executor_enabled=cfg.executor_enabled,
        agent=cfg.agent,
        merge_enabled=cfg.merge_enabled,
        require_checks=cfg.require_checks,
        repos=[r.name for r in cfg.active_repos()],
        repos_disabled=[r.name for r in cfg.repos if not r.enabled],
        repos_total=len(cfg.repos),
        missing_clones=missing_clones,
        graphs=graphs,
        mill_ready=mill_ready,
        blockers=blockers,
        idle=idle,
        health=survey.get("health"),
        remaining=remaining,
        survey_ok=survey.get("ok"),
        work_units=work,
        live_env_hint=live_env_hint if not mill_ready else None,
    )
    if not idle and not mill_ready:
        payload["ok"] = False
        payload["error"] = "not working: work remains but mill is not live-ready"
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
    args = p.parse_args(argv)
    return emit_exit(compose_status(config_path=args.config))


if __name__ == "__main__":
    raise SystemExit(main())
