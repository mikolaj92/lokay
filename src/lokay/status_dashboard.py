"""Read-only local data model for the Lokay status dashboard."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from lokay.compose.status import compose_status
from lokay.config import load_config
from lokay.pass_history import read_pass_history
from lokay.proc.yield_report import build_report


def _counts(report: dict[str, Any]) -> dict[str, int]:
    rows = report.get("by_repo") or {}
    return {
        name: sum(int((values or {}).get(name) or 0) for values in rows.values())
        for name in ("starts", "prs", "merges", "failures")
    }


def dashboard_snapshot(config_path: str | None, *, history_limit: int = 50) -> dict[str, Any]:
    """Combine authoritative local status, event yield, catalog and pass history."""
    cfg = load_config(config_path)
    status = compose_status(config_path=config_path, survey=False)
    now = datetime.now(timezone.utc)
    windows: dict[str, Any] = {}
    for label, delta in (("24h", timedelta(hours=24)), ("7d", timedelta(days=7))):
        report = build_report(cfg.state_path, since=now - delta)
        windows[label] = {**_counts(report), "events": int(report.get("events") or 0)}
    catalog = [
        {
            "name": repo.name,
            "priority": repo.priority,
            "enabled": repo.enabled,
            "clone_path": str(repo.clone_path),
            "clone_available": repo.clone_path.exists(),
            "note": repo.note,
        }
        for repo in cfg.repos
    ]
    history = read_pass_history(state_path=cfg.state_path, limit=history_limit)
    last_pass = status.get("last_pass")
    if not history and isinstance(last_pass, dict):
        history = [last_pass]
    return {
        "generated_at": now.isoformat(),
        "status": status,
        "throughput": windows,
        "catalog": catalog,
        "history": history,
    }
