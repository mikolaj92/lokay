"""Stuck-issue ledger: one failing ready issue must not block the lokay.

Persists failure counts next to state.jsonl so subsequent ticks apply a
*local cooldown* (never ai:frozen / eternal stuck limbo) for issues that
keep failing. Dark factory legal exits remain ready | split | skip |
close+reason — verify / no_pr failures must not permanently bury OPEN ready.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


# Local cooldown for verify / no_delivery / no_pr fail-closed rows.
# Never a permanent ledger bury (lokay#1082).
TRANSIENT_LEDGER_REASONS = frozenset(
    {
        "no_pr",
        "local_repair_exhausted",
        "test_local_recheck_failed",
        "test_local_failed",
        "test_local_missing",
        "repair_agent_failed",
    }
)
TRANSIENT_COOLDOWN_SECONDS = 300


def stuck_path_for(state_path: Path) -> Path:
    """Default ledger path beside the event log."""
    return state_path.with_name("stuck.json")


def issue_key(repo: str, number: int) -> str:
    return f"{repo}#{int(number)}"


def is_transient_ledger_reason(reason: str | None) -> bool:
    return str(reason or "").strip() in TRANSIENT_LEDGER_REASONS


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(raw: Any) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def block_active(row: dict[str, Any] | None, *, now: datetime | None = None) -> bool:
    """True only while a blocked stamp is still within its local cooldown.

    Legacy transient rows (no_pr / verify) written as eternal ``blocked:true``
    without ``cooldown_until`` are inactive — they must not exclude OPEN ready.
    Non-transient terminal miss rows without cooldown stay active (bound skip).
    """
    if not isinstance(row, dict) or not row.get("blocked"):
        return False
    reason = str(row.get("reason") or "")
    cooldown_until = _parse_ts(row.get("cooldown_until"))
    if cooldown_until is not None:
        stamp = now or _utcnow()
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        return cooldown_until > stamp
    # Legacy eternal transient limbo → treat as expired (auto-clear path).
    if is_transient_ledger_reason(reason):
        return False
    return True


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
    """Persist ledger. Never immortalize expired / legacy-transient blocked rows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    on_disk = load_stuck(path)
    on_disk_issues = on_disk.get("issues")
    incoming_issues = data.get("issues")
    cleared = {str(key) for key in list(data.get("cleared") or []) if str(key)}
    if isinstance(on_disk_issues, dict) and isinstance(incoming_issues, dict):
        blocked_not_incoming = {
            key: row
            for key, row in on_disk_issues.items()
            if key not in incoming_issues
            and key not in cleared
            and isinstance(row, dict)
            and block_active(row)
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
            if key not in cleared
            and isinstance(row, dict)
            and block_active(row)
        }
        if blocked_on_disk:
            data = {**data, "issues": blocked_on_disk}
    # Drop inactive blocked stamps so dark factory cannot re-bury via merge.
    issues = data.get("issues")
    if isinstance(issues, dict):
        for key, row in list(issues.items()):
            if not isinstance(row, dict) or not row.get("blocked"):
                continue
            if block_active(row):
                continue
            if is_transient_ledger_reason(str(row.get("reason") or "")):
                issues.pop(key, None)
                cleared_list = data.setdefault("cleared", [])
                if key not in cleared_list:
                    cleared_list.append(key)
            else:
                # Expired explicit cooldown on a non-transient row: clear flag.
                row = dict(row)
                row.pop("blocked", None)
                row.pop("blocked_ts", None)
                row.pop("cooldown_until", None)
                row.pop("cooldown_seconds", None)
                issues[key] = row
    persist = {key: value for key, value in data.items() if key != "cleared"}
    path.write_text(json.dumps(persist, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def failure_count(data: dict[str, Any], repo: str, number: int) -> int:
    row = (data.get("issues") or {}).get(issue_key(repo, number)) or {}
    return int(row.get("failures") or 0)


def is_blocked_in_ledger(data: dict[str, Any], repo: str, number: int) -> bool:
    key = issue_key(repo, number)
    row = (data.get("issues") or {}).get(key) or {}
    if not isinstance(row, dict):
        return False
    if block_active(row):
        return True
    # Auto-clear inactive transient limbo so survey sees OPEN ready again.
    if row.get("blocked") and is_transient_ledger_reason(str(row.get("reason") or "")):
        clear_issue(data, repo, number)
    return False


def excluded_numbers(data: dict[str, Any], repo: str) -> set[int]:
    """Issue numbers for this repo that should be skipped (active cooldown only)."""
    out: set[int] = set()
    prefix = f"{repo}#"
    for key, row in list((data.get("issues") or {}).items()):
        if not str(key).startswith(prefix):
            continue
        if not isinstance(row, dict):
            continue
        if block_active(row):
            try:
                out.add(int(str(key).split("#", 1)[1]))
            except ValueError:
                continue
            continue
        if row.get("blocked") and is_transient_ledger_reason(str(row.get("reason") or "")):
            try:
                number = int(str(key).split("#", 1)[1])
            except ValueError:
                continue
            clear_issue(data, repo, number)
    return out


def record_failure(
    data: dict[str, Any],
    *,
    repo: str,
    number: int,
    error: str = "",
    max_failures: int = 2,
    reason: str = "",
    cooldown_seconds: int | None = None,
) -> dict[str, Any]:
    """Increment failure count. Optional local cooldown — never eternal limbo for transient reasons."""
    issues = data.setdefault("issues", {})
    key = issue_key(repo, number)
    row = dict(issues.get(key) or {})
    row["failures"] = int(row.get("failures") or 0) + 1
    row["last_error"] = (error or "")[:500]
    now = _utcnow()
    row["last_ts"] = now.isoformat()
    stamped_reason = str(reason or row.get("reason") or "").strip()
    if stamped_reason:
        row["reason"] = stamped_reason
    should_block = row["failures"] >= max(1, int(max_failures))
    if should_block:
        row["blocked"] = True
        row["blocked_ts"] = row["last_ts"]
        cd = cooldown_seconds
        if cd is None and is_transient_ledger_reason(stamped_reason):
            cd = TRANSIENT_COOLDOWN_SECONDS
        if cd is not None:
            seconds = max(1, int(cd))
            row["cooldown_seconds"] = seconds
            row["cooldown_until"] = (now + timedelta(seconds=seconds)).isoformat()
        else:
            # Non-transient terminal skip: no cooldown_until (bound miss).
            row.pop("cooldown_until", None)
            row.pop("cooldown_seconds", None)
    issues[key] = row
    return row


def clear_issue(data: dict[str, Any], repo: str, number: int) -> None:
    """Drop a ledger row and remember it so save_stuck cannot restore it."""
    key = issue_key(repo, number)
    issues = data.get("issues") or {}
    issues.pop(key, None)
    cleared = data.setdefault("cleared", [])
    if key not in cleared:
        cleared.append(key)


def issue_number_from_branch(head_ref: str, *, branch_prefix: str = "ai/fix") -> int | None:
    """Parse issue number from lokay leftover branches. Harvest leftovers are not lokay issues."""
    prefix = branch_prefix.rstrip("/") + "/"
    ref = (head_ref or "").strip()
    if not ref.startswith(prefix):
        return None
    rest = ref[len(prefix) :]
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
    issue_to_pr lokay (avoids duplicate work / agent never needed again).
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
