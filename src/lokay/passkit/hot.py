"""Pick which repos a factory pass must survey live.

A 29-repo walk eats the 5–10 min cycle before implement. Repos that last
pass already showed empty (no inbox, ready, or AI PR) stay cold: surveys
skip GitHub and treat them as empty. Always re-walk last-pass hot repos
plus a couple of rotated cold ones so new work still wakes up.
"""

from __future__ import annotations

import json
import zlib
from pathlib import Path
from typing import Any


def repo_is_hot(row: dict[str, Any] | None) -> bool:
    if not isinstance(row, dict):
        return False
    return bool(
        int(row.get("inbox") or 0)
        or int(row.get("ready") or 0)
        or int(row.get("open_ai_prs") or 0)
        or int(row.get("actionable_open_ai_prs") or 0)
        or row.get("occupied")
        or row.get("survey_error")
    )


def load_last_pass_by_repo(state_path: str | Path | None) -> dict[str, dict[str, Any]]:
    if not state_path:
        return {}
    receipt = Path(state_path).expanduser().resolve().parent / "last-pass.json"
    try:
        payload = json.loads(receipt.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    remaining = payload.get("remaining") if isinstance(payload, dict) else None
    rows = remaining.get("by_repo") if isinstance(remaining, dict) else None
    if not isinstance(rows, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict) and row.get("repo"):
            out[str(row["repo"])] = row
    return out


def pick_survey_repos(
    repos: list[str],
    prev_by_repo: dict[str, dict[str, Any]],
    *,
    salt: str = "",
    extra_cold: int = 2,
) -> list[str]:
    names = [str(name) for name in repos if name]
    if not names:
        return []
    hot = [name for name in names if repo_is_hot(prev_by_repo.get(name))]
    # Keep the leading configured lanes stable so equal-priority repos retain
    # their config order (priority, then name). Rotate only the final discovery
    # lane; rotating the whole cold window makes K dispatch order random.
    anchor = [name for name in names if name == "mikolaj92/lokay"] if not hot else []
    fixed = set(hot) | set(anchor)
    cold = [name for name in names if name not in fixed]
    if not cold or extra_cold <= 0:
        return [*hot, *anchor] or names
    width = min(extra_cold, len(cold))
    # Without the lokay anchor, ``extra_cold`` is also the K dispatch breadth.
    # Keep all K lanes stable and add one rotated discovery lane when available.
    stable_count = width if not hot and not anchor else max(0, width - 1)
    stable = cold[:stable_count]
    remaining = cold[stable_count:]
    rotated = []
    if remaining:
        rotated = [remaining[zlib.adler32(salt.encode("utf-8")) % len(remaining)]]
    return list(dict.fromkeys([*hot, *anchor, *stable, *rotated]))


def survey_scope(begin: dict[str, Any]) -> list[str] | None:
    """None means walk every begin.repos (tests / first pass)."""
    scoped = begin.get("survey_repos")
    if not isinstance(scoped, list) or not scoped:
        return None
    return [str(name) for name in scoped if name]
