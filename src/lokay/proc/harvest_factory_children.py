"""Invoke the authored detached-child harvest subflow."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any


def resolve_harvest_args(
    config: dict | None, scope: dict | None, ledger: dict | None
) -> dict[str, Any]:
    """Fill state_path / repos / stuck ledger when the Fala atom omits them.

    ``harvest_factory_children`` is the first factory_pass effector: conduction
    carries no upstream read_factory_stuck receipt, so the organ must resolve
    the ledger from config (lokay#1094).
    """
    from lokay.factory_scope import factory_repo, scoped_repos
    from lokay.proc._common import load_cfg
    from lokay.stuck import load_stuck, stuck_path_for

    config = dict(config or {})
    scope = dict(scope or {})
    ledger = dict(ledger or {})

    config_path = (
        str(config.get("config_path") or scope.get("config_path") or "") or None
    )
    live = bool(config["live"]) if "live" in config else True
    state_path = str(config.get("state_path") or "") or None
    repos = [str(repo).strip() for repo in (scope.get("repos") or []) if str(repo).strip()]

    needs_cfg = bool(config_path) or not state_path or not repos
    if needs_cfg:
        cfg = load_cfg(argparse.Namespace(config=config_path, live=live))
        if cfg.config_path:
            config_path = str(cfg.config_path)
        state_path = state_path or str(cfg.state_path)
        if not repos:
            configured = [str(row.name) for row in cfg.active_repos()]
            repos, _ = scoped_repos(configured, lokay=factory_repo())

    if not state_path:
        raise KeyError("state_path")

    config["state_path"] = state_path
    config["config_path"] = config_path
    config["live"] = live
    scope["config_path"] = config_path
    scope["repos"] = repos

    if not str(ledger.get("stuck_path") or "").strip():
        path = stuck_path_for(Path(state_path))
        stuck = load_stuck(path)
        issues = stuck.get("issues") or {}
        ledger = {
            "stuck_path": str(path),
            "stuck": stuck,
            "issue_count": len(issues) if isinstance(issues, dict) else 0,
        }

    return {"config": config, "scope": scope, "ledger": ledger}


def harvest(config: dict, scope: dict, ledger: dict) -> dict:
    from lokay.proc.child_harvest_subflow import run
    from lokay.proc.factory_begin_receipt import harvest_receipt, with_stuck

    resolved = resolve_harvest_args(config, scope, ledger)
    return harvest_receipt(
        run(resolved["config"], resolved["scope"], with_stuck(resolved["ledger"]))
    )
