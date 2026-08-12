"""Bounded GitHub survey budget helpers (429 detection + pacing)."""

from __future__ import annotations

import re
import time
from typing import Any

_RATE_LIMIT_RE = re.compile(
    r"(?i)(\b429\b|rate[- ]?limit|secondary rate|API rate limit exceeded|abuse detection)"
)


def is_rate_limit_text(*parts: str) -> bool:
    blob = "\n".join(p for p in parts if p)
    if not blob:
        return False
    return bool(_RATE_LIMIT_RE.search(blob))


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
