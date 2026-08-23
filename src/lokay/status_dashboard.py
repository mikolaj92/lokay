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
    windows_spec = (
        ("1h", timedelta(hours=1)),
        ("24h", timedelta(hours=24)),
        ("7d", timedelta(days=7)),
    )
    for label, delta in windows_spec:
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
    last_pass = status.get("last_pass")
    remaining = last_pass.get("remaining") if isinstance(last_pass, dict) else {}
    if not isinstance(remaining, dict):
        remaining = {}
    backlog = {
        # Disjoint issue queues. ready_with_open_pr overlaps ready and stays diagnostic only.
        "open_issues": int(remaining.get("inbox") or 0) + int(remaining.get("ready") or 0),
        "inbox": int(remaining.get("inbox") or 0),
        "ready": int(remaining.get("ready") or 0),
        "ready_with_open_pr": int(remaining.get("ready_with_open_pr") or 0),
        "open_ai_prs": int(remaining.get("open_ai_prs") or 0),
        "review_limbo": int(remaining.get("review_limbo") or 0),
        "needs_repair": int(remaining.get("needs_repair") or 0),
        "survey_errors": int(remaining.get("survey_errors") or 0),
    }
    one_hour = windows["1h"]
    kpis = {
        "issues_per_hour": int(one_hour.get("merges") or 0),
        "starts_per_hour": int(one_hour.get("starts") or 0),
        "prs_per_hour": int(one_hour.get("prs") or 0),
        "failures_per_hour": int(one_hour.get("failures") or 0),
        "open_issues": backlog["open_issues"],
    }
    history = read_pass_history(state_path=cfg.state_path, limit=history_limit)
    if not history and isinstance(last_pass, dict):
        history = [last_pass]
    return {
        "generated_at": now.isoformat(),
        "status": status,
        "throughput": windows,
        "kpis": kpis,
        "backlog": backlog,
        "catalog": catalog,
        "history": history,
    }
