"""Persist one issue-department receipt. One job: write."""

from __future__ import annotations

import json
from pathlib import Path


def write(summary: dict, *, pass_dir: str = "") -> dict:
    result = dict(summary.get("result") or {})
    if not pass_dir:
        return {"ok": True, "result": result, "applied": False}
    path = Path(pass_dir) / "issues-receipt.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    result["receipt"] = str(path)
    return {"ok": True, "result": result, "applied": True}
