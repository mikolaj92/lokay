"""Clear stale metric-only cycle starts using collected CLOSED catalog facts."""

import json
from pathlib import Path

from lokay.child_harvest import _as_int


def clear(facts: dict) -> dict:
    root = Path(facts["cycle_dir"])
    allowed = set(facts.get("repos") or [])
    closed = {k: set(v) for k, v in (facts.get("closed_catalog") or {}).items()}
    if root.is_dir() and allowed:
        for path in root.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, ValueError):
                continue
            if (
                not isinstance(data, dict)
                or "pid" in data
                or data.get("starting") is True
            ):
                continue
            repo = str(data.get("repo") or "")
            issue = _as_int(data.get("issue"))
            if (
                repo
                and issue is not None
                and (repo not in allowed or issue in closed.get(repo, set()))
            ):
                try:
                    path.unlink()
                except OSError:
                    pass
    return facts
