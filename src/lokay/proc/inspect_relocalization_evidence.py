"""Read one localize evidence object and its bounded path list."""

import json
from pathlib import Path


def inspect(*, worktree: str) -> dict:
    root = Path(worktree).resolve()
    path = root / ".lokay/localize.json"
    if not root.is_dir() or not path.is_file():
        return {
            "ok": True,
            "route": "terminal",
            "reason": "no_localize",
            "worktree": str(root),
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        paths = [
            str(x).removeprefix("./").rstrip("/")
            for x in data.get("paths", [])
            if str(x).strip()
        ]
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": True,
            "route": "terminal",
            "reason": "invalid_localize",
            "error": str(exc),
            "worktree": str(root),
        }
    return {"ok": True, "route": "read", "worktree": str(root), "localized": paths}
