"""Read production delivery facts from GitHub, the Definition-of-Done source."""

from __future__ import annotations

import json
import statistics
from datetime import datetime, timezone
from typing import Any

from lokay.runner import Runner, gh_spec


def _ts(raw: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _minutes(rows: list[dict[str, Any]], start: str, end: str) -> list[float]:
    out: list[float] = []
    for row in rows:
        first, last = _ts(row.get(start)), _ts(row.get(end))
        if first is not None and last is not None:
            out.append((last - first).total_seconds() / 60)
    return out


def _summary(rows: list[dict[str, Any]], *, hours: float, start: str, end: str) -> dict[str, Any]:
    durations = sorted(_minutes(rows, start, end))
    p90 = durations[max(0, int(len(durations) * 0.9) - 1)] if durations else None
    return {
        "count": len(rows),
        "per_hour": round(len(rows) / hours, 2) if hours > 0 else 0,
        "median_minutes": round(statistics.median(durations), 1) if durations else None,
        "p90_minutes": round(p90, 1) if p90 is not None else None,
    }


def github_delivery(runner: Runner, repo: str, *, since: datetime, hours: float) -> dict[str, Any]:
    cutoff = since.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    pulls = runner.run_checked(
        gh_spec(["api", "--paginate", f"repos/{repo}/pulls?state=closed&per_page=100"], timeout_seconds=120),
        live=True,
    )
    issues = runner.run_checked(
        gh_spec(["api", "--paginate", f"repos/{repo}/issues?state=closed&per_page=100"], timeout_seconds=120),
        live=True,
    )
    pull_rows = json.loads(pulls.stdout or "[]")
    issue_rows = json.loads(issues.stdout or "[]")
    merged = [row for row in pull_rows if row.get("merged_at") and str(row["merged_at"]) >= cutoff]
    closed = [
        row for row in issue_rows
        if "pull_request" not in row and row.get("closed_at") and str(row["closed_at"]) >= cutoff
    ]
    return {
        "repo": repo,
        "source": "github",
        "merged_prs": _summary(merged, hours=hours, start="created_at", end="merged_at"),
        "closed_issues": _summary(closed, hours=hours, start="created_at", end="closed_at"),
    }
