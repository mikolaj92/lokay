"""Bounded GitHub survey budget helpers (429 detection + pacing)."""

from __future__ import annotations

import json
import re
import time
from typing import Any

_RATE_LIMIT_RE = re.compile(
    r"(?i)(\b429\b|rate[- ]?limit|secondary rate|API rate limit exceeded|abuse detection)"
)
_SERVICE_TRANSIENT_RE = re.compile(
    r"(?i)(?:\bHTTP\s+(?:429|500|502|503|504)\b|"
    r"\b(?:502 Bad Gateway|503 Service Unavailable|504 Gateway Timeout)\b|"
    r"No server is currently available)"
)

# gh issue/pr list is newest-first. A silent page cap starves oldest ready
# tickets (select_issue is oldest-first on whatever the survey returned).
SURVEY_LIST_CAP = 1000


def is_rate_limit_text(*parts: str) -> bool:
    blob = "\n".join(p for p in parts if p)
    if not blob:
        return False
    return bool(_RATE_LIMIT_RE.search(blob))


def is_transient_github_text(*parts: str) -> bool:
    """Whether a failed ``gh`` command is GitHub/rate-limit uncertainty.

    This intentionally describes the transport/service response, not a red CI
    result. Callers must keep the result non-green and wait rather than repair
    or merge while GitHub cannot authoritatively report the PR state.
    """
    blob = "\n".join(p for p in parts if p)
    return bool(blob) and (
        is_rate_limit_text(blob) or bool(_SERVICE_TRANSIENT_RE.search(blob))
    )


def survey_pace(cfg: Any | None, *, sleep_fn=time.sleep) -> None:
    """Optional inter-call delay so multi-repo surveys are less bursty."""
    if cfg is None:
        return
    try:
        ms = int(getattr(cfg, "gh_survey_pace_ms", 0) or 0)
    except (TypeError, ValueError):
        return
    if ms <= 0:
        return
    sleep_fn(min(ms, 60_000) / 1000.0)


def backoff_seconds(attempt: int) -> float:
    """Exponential backoff capped at 32s (attempt is 0-based)."""
    return float(min(32, 2 ** max(0, attempt)))


def survey_list_cap(limit: int | None = None) -> int:
    """Hard ceiling for one gh issue/pr list. Callers must fail closed if hit."""
    requested = SURVEY_LIST_CAP if limit is None else int(limit)
    return max(1, min(requested, SURVEY_LIST_CAP))


def parse_survey_list(
    stdout: str,
    *,
    kind: str,
    repo: str,
    cap: int,
    on_cap: str = "fail",
) -> list[Any]:
    """Decode a gh list JSON array. Hitting ``cap`` is a truncated page, not idle.

    Survey callers keep ``on_cap="fail"``. The issues child keeps the page
    (``on_cap="keep"``) so overflow is leftover skip, not a failed pass.
    """
    rows = json.loads(stdout or "[]")
    if not isinstance(rows, list):
        raise RuntimeError(f"{kind} survey on {repo} returned non-list JSON")
    if len(rows) >= cap:
        if on_cap == "keep":
            return rows
        raise RuntimeError(
            f"{kind} survey on {repo} hit the {cap} newest-first cap; "
            "refuse a silent truncated queue"
        )
    return rows
