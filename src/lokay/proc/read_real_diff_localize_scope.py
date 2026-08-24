"""Read and validate one optional localization evidence file."""

import json
from pathlib import Path


def read(worktree: dict) -> dict:
    if worktree.get("route") != "read":
        return {"ok": True, "route": "unused", "paths": []}
    path = Path(worktree["worktree"]) / ".lokay/localize.json"
    if not path.is_file():
        return {"ok": True, "route": "none", "paths": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        paths = payload.get("paths", []) if isinstance(payload, dict) else None
        if not isinstance(paths, list) or not all(isinstance(x, str) for x in paths):
            raise ValueError("paths must be a list of strings")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return {
            "ok": True,
            "route": "terminal",
            "reason": "invalid_localize",
            "error": str(exc),
            "paths": [],
        }
    return {
        "ok": True,
        "route": "scope",
        "paths": [x.removeprefix("./").rstrip("/") for x in paths if x.rstrip("/")],
    }
