"""Read finished detached issue_to_pr children into the existing stuck ledger.

Not a second journal. Receipts live in ``~/.lokay/cycle/*.json``; the child's
result is already in ``state.jsonl`` (compose) or the Fala i2pr sqlite (read
only). Fail-closed reasons skip the next survey via ``stuck.json``.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Callable

from lokay.proc.detach_issue_to_pr import is_live_issue_to_pr_pid
from lokay.stuck import is_blocked_in_ledger, record_failure

FAIL_CLOSED = frozenset(
    {
        "local_repair_exhausted",
        "test_local_recheck_failed",
        "test_local_failed",
        "test_local_missing",
        "repair_agent_failed",
        "zero_diff",
        "invalid_branch_ref",
    }
)

_WORKTREE_FAIL_MARKERS = (
    "worktree add failed",
    "invalid_branch_ref",
    "invalid branch ref",
    "not a valid branch",
    "check-ref-format",
)


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


_REASON_PRIORITY = (
    "invalid_branch_ref",
    "local_repair_exhausted",
    "test_local_recheck_failed",
    "test_local_failed",
    "test_local_missing",
    "repair_agent_failed",
    "zero_diff",
)


def _reason_from_text(text: str) -> str | None:
    if not text:
        return None
    low = text.lower()
    if any(marker in low for marker in _WORKTREE_FAIL_MARKERS):
        return "invalid_branch_ref"
    for token in _REASON_PRIORITY:
        if token in text:
            return token
    return None


def _walk_text(value: Any, chunks: list[str], *, depth: int = 0) -> None:
    """Collect strings from a child envelope, including nested adapter JSON."""
    if depth > 8 or value in (None, "", {}, []):
        return
    if isinstance(value, str):
        chunks.append(value)
        start = value.find("{")
        if start >= 0 and "}" in value[start:]:
            try:
                parsed = json.loads(value[start:])
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, (dict, list)):
                _walk_text(parsed, chunks, depth=depth + 1)
        return
    if isinstance(value, dict):
        for item in value.values():
            _walk_text(item, chunks, depth=depth + 1)
        return
    if isinstance(value, list):
        for item in value[:80]:
            _walk_text(item, chunks, depth=depth + 1)
        return
    chunks.append(str(value))


def _classify(event: dict[str, Any] | None) -> str | None:
    if not event or event.get("ok") is not False:
        return None
    reason = event.get("reason")
    if isinstance(reason, str) and reason in FAIL_CLOSED:
        return reason
    chunks: list[str] = []
    if isinstance(reason, str):
        chunks.append(reason)
    _walk_text(event, chunks)
    return _reason_from_text("\n".join(chunks))


def _index_issue_to_pr_events(state_path: Path) -> dict[tuple[str, int], dict[str, Any]]:
    """One pass over state.jsonl → last issue_to_pr event per (repo, issue)."""
    index: dict[tuple[str, int], dict[str, Any]] = {}
    if not state_path.is_file():
        return index
    try:
        fh = state_path.open(encoding="utf-8")
    except OSError:
        return index
    with fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(ev, dict) or ev.get("kind") != "issue_to_pr":
                continue
            repo = str(ev.get("repo") or "")
            issue = _as_int(ev.get("issue"))
            if not repo or issue is None:
                continue
            index[(repo, issue)] = ev
    return index


def _last_issue_to_pr_event(state_path: Path, repo: str, issue: int) -> dict[str, Any] | None:
    return _index_issue_to_pr_events(state_path).get((repo, issue))


def _fala_i2pr_db(repo: str, issue: int, home: Path) -> Path:
    owner, name = repo.split("/", 1)
    return home / ".lokay" / "fala" / "i2pr" / f"{owner}__{name}__{issue}" / "state.sqlite"


def _event_from_fala_journal(repo: str, issue: int, home: Path) -> dict[str, Any] | None:
    """Read-only fallback: existing Fala i2pr journal. Never create the file."""
    if "/" not in repo:
        return None
    db = _fala_i2pr_db(repo, issue, home)
    if not db.is_file():
        return None
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            rows = con.execute(
                "SELECT status, output_json, error_json FROM processes "
                "ORDER BY updated_at DESC"
            ).fetchall()
        finally:
            con.close()
    except sqlite3.Error:
        return None
    blobs: list[str] = []
    for status, output_json, error_json in rows:
        if str(status or "").lower() != "failed":
            continue
        blobs.append(f"{error_json or ''}\n{output_json or ''}")
    if not blobs:
        return None
    reason = None
    chosen = ""
    for blob in blobs:
        found = _reason_from_text(blob)
        if not found:
            continue
        reason = found
        chosen = blob
        if found == "invalid_branch_ref":
            break
    if not reason:
        return None
    return {
        "ok": False,
        "kind": "issue_to_pr",
        "repo": repo,
        "issue": issue,
        "reason": reason,
        "error": chosen[:500],
    }


def _resolved(path: Path) -> Path:
    try:
        return Path(path).expanduser().resolve()
    except OSError:
        return Path(path).expanduser()


def _isolated_mill_roots(state_path: Path, home: Path) -> tuple[Path, Path]:
    """Host mill reads ~/.lokay/cycle; a tmp mill must not inherit it."""
    host_state = _resolved(Path(home) / ".lokay" / "state.jsonl")
    state = _resolved(Path(state_path))
    if state == host_state:
        return Path(home) / ".lokay" / "cycle", Path(home)
    return state.parent / "cycle", state.parent


def harvest_fail_closed_children(
    stuck: dict[str, Any],
    *,
    state_path: Path,
    cycle_dir: Path | None = None,
    is_live: Callable[[int], bool] | None = None,
    home: Path | None = None,
) -> dict[str, Any]:
    """Block tickets whose detached child already died fail-closed.

    Live pids are left alone. Dead pid + no event + no machine reason is
    treated as transient (retry), not fail-closed.
    """
    home_root = Path(home) if home is not None else Path.home()
    default_cycle, isolated_home = _isolated_mill_roots(state_path, home_root)
    root = Path(cycle_dir) if cycle_dir is not None else default_cycle
    if home is None:
        home_root = isolated_home
    check = is_live or is_live_issue_to_pr_pid
    if not root.is_dir():
        return stuck

    events = _index_issue_to_pr_events(state_path)
    for path in sorted(root.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        repo = str(data.get("repo") or "")
        issue = _as_int(data.get("issue"))
        if not repo or issue is None:
            continue
        if is_blocked_in_ledger(stuck, repo, issue):
            continue
        # cycle_start writes repo/issue/started_ts only. Harvest source is
        # the detach receipt (has pid). A start file must not fail-close a
        # still-live sibling.
        if "pid" not in data:
            continue
        pid = _as_int(data.get("pid"))
        if pid is not None and check(pid):
            continue

        event = events.get((repo, issue))
        reason = _classify(event)
        if not reason:
            fallback = _event_from_fala_journal(repo, issue, home_root)
            if fallback is not None:
                event = fallback
                reason = _classify(event)
        if not reason:
            continue
        error = ""
        if event:
            error = str(event.get("error") or event.get("reason") or reason)
        row = record_failure(
            stuck,
            repo=repo,
            number=issue,
            error=error or reason,
            max_failures=1,
        )
        row["blocked"] = True
        row["reason"] = reason
    return stuck
