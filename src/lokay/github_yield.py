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


def _flatten_api_pages(stdout: str, *, kind: str) -> list[dict[str, Any]]:
    """Accept gh --paginate JSON streams and explicit --slurp page arrays."""
    decoder = json.JSONDecoder()
    raw = str(stdout or "").strip()
    values: list[Any] = []
    offset = 0
    try:
        while offset < len(raw):
            value, offset = decoder.raw_decode(raw, offset)
            values.append(value)
            while offset < len(raw) and raw[offset].isspace():
                offset += 1
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{kind} GitHub yield returned invalid JSON: {exc}") from exc
    rows: list[dict[str, Any]] = []
    for value in values:
        pages = value if isinstance(value, list) else None
        if pages is None:
            raise RuntimeError(f"{kind} GitHub yield returned non-list JSON")
        for page in pages:
            if isinstance(page, list):
                rows.extend(row for row in page if isinstance(row, dict))
            elif isinstance(page, dict):
                rows.append(page)
    return rows


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
    # Yield pagination is flattened before row access.
    pull_rows = _flatten_api_pages(pulls.stdout, kind="pull")
    issue_rows = _flatten_api_pages(issues.stdout, kind="issue")
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
