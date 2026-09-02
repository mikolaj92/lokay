"""Read-only projection of durable issue-delivery work units."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def work_id(repo: str, issue: int) -> str:
    return f"{str(repo).strip()}#{int(issue)}"


def _as_issue(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _delivered(event: dict[str, Any]) -> bool:
    if event.get("delivered") is True:
        return True
    if event.get("delivered") is False:
        return False
    try:
        return int(event.get("pr")) > 0
    except (TypeError, ValueError):
        return str(event.get("reason") or "") in {
            "issue_closed",
            "delivery_pr_exists",
        }


def _state(event: dict[str, Any]) -> str:
    if _delivered(event):
        return "delivered"
    explicit = str(event.get("work_state") or "").strip()
    if explicit:
        return explicit
    reason = str(event.get("reason") or "").strip()
    if reason:
        return reason
    return "stopped" if event.get("stopped") else "observed"


def _project(event: dict[str, Any]) -> dict[str, Any]:
    repo = str(event["repo"])
    issue = int(event["issue"])
    projected = {
        "work_id": work_id(repo, issue),
        "repo": repo,
        "issue": issue,
        "state": _state(event),
        "delivered": _delivered(event),
    }
    for source, target in (
        ("pr", "pr"),
        ("branch", "branch"),
        ("run_id", "run_id"),
        ("ts", "updated_at"),
    ):
        value = event.get(source)
        if value not in (None, ""):
            projected[target] = value
    return projected


def project_work_units(state_path: Path) -> list[dict[str, Any]]:
    """Fold issue-to-PR events by stable identity; delivery is monotonic."""
    units: dict[str, dict[str, Any]] = {}
    try:
        lines = Path(state_path).read_text(encoding="utf-8").splitlines()
    except (FileNotFoundError, OSError):
        return []
    for line in lines:
        try:
            event = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(event, dict) or event.get("kind") != "issue_to_pr":
            continue
        repo = str(event.get("repo") or "").strip()
        issue = _as_issue(event.get("issue"))
        if not repo or issue is None:
            continue
        event = {**event, "repo": repo, "issue": issue}
        key = work_id(repo, issue)
        previous = units.get(key)
        candidate = _project(event)
        if previous is None or candidate["delivered"] or not previous["delivered"]:
            units[key] = candidate
    return list(units.values())


def status_work_units(
    units: list[dict[str, Any]], *, limit: int = 20
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Return a bounded operational view and the latest durable delivery."""
    deliveries = [row for row in units if row.get("delivered")]
    latest = deliveries[-1] if deliveries else None
    pending = [row for row in units if not row.get("delivered")]
    chosen: list[dict[str, Any]] = pending[-max(0, int(limit)) :]
    remaining = max(0, int(limit) - len(chosen))
    if remaining:
        chosen = deliveries[-remaining:] + chosen
    return chosen[-max(0, int(limit)) :], latest
