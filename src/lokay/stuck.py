"""Stuck-issue ledger: one failing ready issue must not block the mill.

Persists failure counts next to state.jsonl so subsequent ticks skip
(and eventually label ai:blocked) issues that keep failing.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def stuck_path_for(state_path: Path) -> Path:
    """Default ledger path beside the event log."""
    return state_path.with_name("stuck.json")


def issue_key(repo: str, number: int) -> str:
    return f"{repo}#{int(number)}"


def load_stuck(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"issues": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"issues": {}}
    if not isinstance(data, dict):
        return {"issues": {}}
    issues = data.get("issues")
    if not isinstance(issues, dict):
        data["issues"] = {}
    return data


def save_stuck(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    on_disk = load_stuck(path)
    on_disk_issues = on_disk.get("issues")
    incoming_issues = data.get("issues")
    if isinstance(on_disk_issues, dict) and isinstance(incoming_issues, dict):
        blocked_not_incoming = {
            key: row
            for key, row in on_disk_issues.items()
            if key not in incoming_issues
            and isinstance(row, dict)
            and row.get("blocked") is True
        }
        if blocked_not_incoming:
            data = {
                **data,
                "issues": {**blocked_not_incoming, **incoming_issues},
            }
    elif isinstance(on_disk_issues, dict):
        blocked_on_disk = {
            key: row
            for key, row in on_disk_issues.items()
            if isinstance(row, dict) and row.get("blocked") is True
        }
        if blocked_on_disk:
            data = {**data, "issues": blocked_on_disk}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def failure_count(data: dict[str, Any], repo: str, number: int) -> int:
    row = (data.get("issues") or {}).get(issue_key(repo, number)) or {}
    return int(row.get("failures") or 0)


def is_blocked_in_ledger(data: dict[str, Any], repo: str, number: int) -> bool:
    row = (data.get("issues") or {}).get(issue_key(repo, number)) or {}
    return bool(row.get("blocked"))


def excluded_numbers(data: dict[str, Any], repo: str) -> set[int]:
    """Issue numbers for this repo that should be skipped (blocked or over threshold)."""
    out: set[int] = set()
    prefix = f"{repo}#"
    for key, row in (data.get("issues") or {}).items():
        if not str(key).startswith(prefix):
            continue
        if not isinstance(row, dict):
            continue
        if row.get("blocked"):
            try:
                out.add(int(str(key).split("#", 1)[1]))
            except ValueError:
                continue
    return out


def record_failure(
    data: dict[str, Any],
    *,
    repo: str,
    number: int,
    error: str = "",
    max_failures: int = 2,
) -> dict[str, Any]:
    """Increment failure count. Returns the updated row; sets blocked when over threshold."""
    issues = data.setdefault("issues", {})
    key = issue_key(repo, number)
    row = dict(issues.get(key) or {})
    row["failures"] = int(row.get("failures") or 0) + 1
    row["last_error"] = (error or "")[:500]
    row["last_ts"] = datetime.now(timezone.utc).isoformat()
    should_block = row["failures"] >= max(1, int(max_failures))
    if should_block:
        row["blocked"] = True
        row["blocked_ts"] = row["last_ts"]
    issues[key] = row
    return row


def clear_issue(data: dict[str, Any], repo: str, number: int) -> None:
    issues = data.get("issues") or {}
    issues.pop(issue_key(repo, number), None)


def issue_number_from_branch(head_ref: str, *, branch_prefix: str = "ai/fix") -> int | None:
    """Parse issue number from `ai/fix/12-slug-deadbeef` style branch names."""
    prefix = branch_prefix.rstrip("/") + "/"
    ref = (head_ref or "").strip()
    if not ref.startswith(prefix):
        # still try generic ai/fix/N-
        if "/" not in ref:
            return None
        rest = ref.split("/", 2)[-1] if ref.count("/") >= 2 else ref.split("/", 1)[-1]
    else:
        rest = ref[len(prefix) :]
    # rest = "12-slug-digest"
    head = rest.split("-", 1)[0]
    if head.isdigit():
        return int(head)
    return None


def issue_numbers_covered_by_prs(
    prs: list[dict[str, Any]],
    *,
    branch_prefix: str = "ai/fix",
) -> set[int]:
    """Issue numbers already represented by open ai/fix/* PR head branches.

    Ready issues with an open agent PR belong to PR triage, not a second
    issue_to_pr mill (avoids duplicate work / agent never needed again).
    """
    out: set[int] = set()
    for pr in prs:
        if not isinstance(pr, dict):
            continue
        n = issue_number_from_branch(
            str(pr.get("head_ref") or ""),
            branch_prefix=branch_prefix,
        )
        if n is not None:
            out.add(n)
    return out
