from __future__ import annotations

import json
from pathlib import Path

RUNS = Path.home() / ".lokay" / "runs"


def run_path(owner: str, repo: str, issue: int) -> Path:
    return RUNS / f"{owner}__{repo.replace('/', '__')}" / f"{issue}.json"


def write_run(owner: str, repo: str, issue: int, fields: dict) -> Path:
    path = run_path(owner, repo, issue)
    path.parent.mkdir(parents=True, exist_ok=True)
    current = json.loads(path.read_text()) if path.exists() else {}
    current.update(fields)
    path.write_text(json.dumps(current, indent=2) + "\n")
    return path


def read_run(owner: str, repo: str, issue: int) -> dict:
    path = run_path(owner, repo, issue)
    if not path.exists():
        return {}
    return json.loads(path.read_text())
