from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

RUNS = Path.home() / ".lokay" / "runs"


def run_dir(repo: str, issue: int) -> Path:
    return RUNS / repo.replace("/", "__") / str(issue)


def state_read(repo: str, issue: int) -> dict:
    path = run_dir(repo, issue) / "state.json"
    return json.loads(path.read_text()) if path.exists() else {}


def state_update(repo: str, issue: int, **fields) -> Path:
    path = run_dir(repo, issue) / "state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    current = json.loads(path.read_text()) if path.exists() else {}
    if "node" in fields and (fields["node"] != current.get("node") or "node_since" not in current):
        import time

        current["node_since"] = time.time()
    current.update(fields)
    from lokay.observe import current as observe_current

    failures = current.get("failures", 0)
    reason = current.get("reason") if failures else None
    result = "failed" if failures and reason else current.get("result", "running")
    if fields.get("failures") == 0 and "result" not in fields and current.get("result") == "failed":
        current["result"] = result = "running"
    observe_current(repo=repo, issue=issue, node=current.get("node"),
                    node_since=current.get("node_since"), result=result,
                    failures=failures, last_error=reason)
    current["updated_at"] = datetime.now(timezone.utc).isoformat()
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(current, indent=2) + "\n")
    temporary.replace(path)
    return path


def rounds_append(repo: str, issue: int, line: str) -> Path:
    path = run_dir(repo, issue) / "rounds.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as stream:
        stream.write(f"- {datetime.now(timezone.utc).isoformat()} {line}\n")
    return path


def run_path(owner: str, repo: str, issue: int) -> Path:
    return run_dir(repo if "/" in repo else f"{owner}/{repo}", issue) / "state.json"


def write_run(owner: str, repo: str, issue: int, fields: dict) -> Path:
    return state_update(repo if "/" in repo else f"{owner}/{repo}", issue, **fields)


def read_run(owner: str, repo: str, issue: int) -> dict:
    return state_read(repo if "/" in repo else f"{owner}/{repo}", issue)
