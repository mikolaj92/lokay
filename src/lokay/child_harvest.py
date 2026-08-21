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

from lokay.mill_scope import mill_repo
from lokay.proc.detach_issue_to_pr import is_live_issue_to_pr_pid
from lokay.runner import Runner, gh_spec
from lokay.stuck import clear_issue, is_blocked_in_ledger, issue_key, record_failure

FAIL_CLOSED = frozenset(
    {
        "local_repair_exhausted",
        "test_local_recheck_failed",
        "test_local_failed",
        "test_local_missing",
        "repair_agent_failed",
        "invalid_branch_ref",
        "no_pr",
        "over_budget",
    }
)

# Product miss: sitko / push / empty compass. Not a spawn crash.
# Count unique runs, not factory_begin ticks. Skip the slot after N;
# do not CLOSE the issue and do not label from harvest.
MISS_REASONS = frozenset(
    {
        "plan_only",
        "zero_diff",
        "push_failed",
        "empty_paths",
        "localize_empty",
        "localize_missing",
        "rebase_conflict",
        "rebase_failed",
        "fetch_failed",
        "rebase_behind_unreadable",
    }
)
MISS_SKIP_AFTER = 3
# One plan-only run is enough: retrying the same ticket just reprints approach.md.
PLAN_ONLY_SKIP_AFTER = 1
# First NFF is the reset shot (worktree -B from origin/main). Second = leave.
PUSH_FAILED_SKIP_AFTER = 2

_WORKTREE_FAIL_MARKERS = (
    "worktree add failed",
    "invalid_branch_ref",
    "invalid branch ref",
    "not a valid branch",
    "check-ref-format",
)


_DELIVERED_REASONS = frozenset(
    {"issue_closed", "delivery_pr_exists", "skipped"}
)


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _event_delivered(event: dict[str, Any] | None) -> bool:
    """ok=True / issue_closed / a PR is delivery, not a vanished crash."""
    if not isinstance(event, dict) or not event:
        return False
    if event.get("ok") is True:
        return True
    reason = event.get("reason")
    if isinstance(reason, str) and reason in _DELIVERED_REASONS:
        return True
    return _as_int(event.get("pr")) is not None


def _clear_stale_no_pr(stuck: dict[str, Any], repo: str, issue: int) -> None:
    key = issue_key(repo, issue)
    row = (stuck.get("issues") or {}).get(key)
    if not isinstance(row, dict):
        return
    reason = str(row.get("reason") or "")
    error = str(row.get("last_error") or "")
    if reason != "no_pr" and "produced no PR" not in error:
        return
    clear_issue(stuck, repo, issue)


def _github_closed_mill_issues(repo: str) -> set[int]:
    """GitHub CLOSED numbers for this mill repo. Empty on probe failure."""
    name = str(repo or "").strip()
    if not name:
        return set()
    try:
        result = Runner().run_checked(
            gh_spec(
                [
                    "issue",
                    "list",
                    "--repo",
                    name,
                    "--state",
                    "closed",
                    "--json",
                    "number,state",
                    "--limit",
                    "1000",
                ],
                timeout_seconds=60,
            ),
            live=True,
        )
        rows = json.loads(result.stdout or "[]")
    except (OSError, RuntimeError, ValueError):
        return set()
    if not isinstance(rows, list):
        return set()
    out: set[int] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("state") or "").upper() != "CLOSED":
            continue
        number = _as_int(row.get("number"))
        if number is not None:
            out.add(number)
    return out


def _clear_github_closed_mill_rows(stuck: dict[str, Any]) -> None:
    """Compacted journals lose issue_closed; GitHub CLOSED is still delivery."""
    mill = mill_repo()
    prefix = f"{mill}#"
    mill_rows = [
        key
        for key in (stuck.get("issues") or {})
        if str(key).startswith(prefix)
    ]
    if not mill_rows:
        return
    closed = _github_closed_mill_issues(mill)
    if not closed:
        return
    for key in mill_rows:
        issue = _as_int(str(key).rpartition("#")[2])
        if issue in closed:
            clear_issue(stuck, mill, issue)


_REASON_PRIORITY = (
    "invalid_branch_ref",
    "no_pr",
    "over_budget",
    "local_repair_exhausted",
    "test_local_recheck_failed",
    "test_local_failed",
    "test_local_missing",
    "repair_agent_failed",
    "rebase_conflict",
    "rebase_failed",
    "fetch_failed",
    "rebase_behind_unreadable",
    "push_failed",
    "plan_only",
    "zero_diff",
    "localize_empty",
    "localize_missing",
    "empty_paths",
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
    known = FAIL_CLOSED | MISS_REASONS
    if isinstance(reason, str) and reason in known:
        return reason
    chunks: list[str] = []
    if isinstance(reason, str):
        chunks.append(reason)
    _walk_text(event, chunks)
    return _reason_from_text("\n".join(chunks))


def _event_run_id(event: dict[str, Any], seq: int) -> str:
    rid = event.get("run_id")
    if rid:
        return str(rid)
    ts = event.get("ts") or event.get("started_ts")
    if ts:
        return f"ts:{ts}"
    return f"seq:{seq}"


def _trailing_miss_runs(
    history: list[tuple[str, str | None]],
) -> tuple[str | None, int]:
    """Unique run_ids of consecutive trailing product misses."""
    last_reason: str | None = None
    seen: list[str] = []
    for run_id, reason in reversed(history):
        if reason not in MISS_REASONS:
            break
        if last_reason is None:
            last_reason = reason
        if run_id not in seen:
            seen.append(run_id)
    return last_reason, len(seen)


def _skip_after(reason: str) -> int:
    if reason == "push_failed":
        return PUSH_FAILED_SKIP_AFTER
    if reason == "plan_only":
        return PLAN_ONLY_SKIP_AFTER
    return MISS_SKIP_AFTER


def _apply_miss_count(
    stuck: dict[str, Any],
    *,
    repo: str,
    issue: int,
    reason: str,
    miss_runs: int,
    error: str,
) -> dict[str, Any]:
    """Reopen only blocked misses below N; preserve terminal miss rows."""
    threshold = _skip_after(reason)
    existing = (stuck.get("issues") or {}).get(f"{repo}#{issue}")
    # Reconciliation repairs only stale one-shot blocks below this miss
    # reason's bound. Once the bound was reached, retain the terminal row
    # verbatim: a dead receipt and its old journal event must not refresh the
    # timestamp/error or make it eligible again on each factory_begin.
    if (
        isinstance(existing, dict)
        and existing.get("blocked")
        and _as_int(existing.get("failures")) is not None
        and int(existing["failures"]) >= threshold
    ):
        return existing
    row = record_failure(
        stuck,
        repo=repo,
        number=issue,
        error=error or reason,
        max_failures=threshold,
    )
    # record_failure increments once per harvest call. Overwrite with
    # the unique-run count so a later tick does not add a phantom miss.
    row["failures"] = miss_runs
    row["reason"] = reason
    if miss_runs >= threshold:
        row["blocked"] = True
    else:
        row.pop("blocked", None)
        row.pop("blocked_ts", None)
    return row


def _index_issue_to_pr_log(
    state_path: Path,
) -> tuple[
    dict[tuple[str, int], dict[str, Any]],
    dict[tuple[str, int], list[tuple[str, str | None]]],
]:
    """One pass: last event + (run_id, reason|ok) history per issue."""
    last: dict[tuple[str, int], dict[str, Any]] = {}
    history: dict[tuple[str, int], list[tuple[str, str | None]]] = {}
    if not state_path.is_file():
        return last, history
    try:
        fh = state_path.open(encoding="utf-8")
    except OSError:
        return last, history
    seq = 0
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
            seq += 1
            key = (repo, issue)
            last[key] = ev
            if ev.get("ok") is True:
                classified: str | None = "ok"
            else:
                classified = _classify(ev)
            history.setdefault(key, []).append((_event_run_id(ev, seq), classified))
    return last, history


def _index_issue_to_pr_events(state_path: Path) -> dict[tuple[str, int], dict[str, Any]]:
    """One pass over state.jsonl to the last issue_to_pr event per issue."""
    last, _history = _index_issue_to_pr_log(state_path)
    return last


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


def _clear_stale_cycle_start_receipts(
    cycle_dir: Path, *, repos: list[str] | None
) -> None:
    """Drop start-only metric files outside mill catalog or GitHub-CLOSED.

    Detach receipts have ``pid`` / ``starting``. Those stay. Unit tests that
    omit ``repos=`` keep hermetic fixtures.
    """
    if repos is None or not cycle_dir.is_dir():
        return
    allowed = {str(name).strip() for name in repos if str(name).strip()}
    if not allowed:
        return
    mill = mill_repo()
    mill_paths: dict[int, Path] = {}
    for path in cycle_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError):
            continue
        if not isinstance(data, dict) or "pid" in data or data.get("starting") is True:
            continue
        repo = str(data.get("repo") or "")
        issue = _as_int(data.get("issue"))
        if not repo or issue is None:
            continue
        if repo not in allowed:
            try:
                path.unlink()
            except OSError:
                pass
            continue
        if repo == mill:
            mill_paths[issue] = path
    if not mill_paths:
        return
    closed = _github_closed_mill_issues(mill)
    if not closed:
        return
    for issue, path in mill_paths.items():
        if issue in closed:
            try:
                path.unlink()
            except OSError:
                pass


def _drop_out_of_scope_stuck_rows(
    stuck: dict[str, Any], repos: list[str] | None
) -> None:
    """Keep only the mill catalog. Omit repos in unit tests so fixtures stay."""
    if repos is None:
        return
    allowed = {str(name).strip() for name in repos if str(name).strip()}
    if not allowed:
        return
    for key in list((stuck.get("issues") or {})):
        repo, sep, num_s = str(key).rpartition("#")
        issue = _as_int(num_s)
        if not sep or not repo or issue is None:
            continue
        if repo not in allowed:
            clear_issue(stuck, repo, issue)
    for key in list(stuck):
        if key in {"issues", "cleared"}:
            continue
        repo, sep, num_s = str(key).rpartition("#")
        issue = _as_int(num_s)
        if not sep or not repo or issue is None:
            continue
        if repo not in allowed:
            stuck.pop(key, None)
            clear_issue(stuck, repo, issue)


def harvest_fail_closed_children(
    stuck: dict[str, Any],
    *,
    state_path: Path,
    cycle_dir: Path | None = None,
    is_live: Callable[[int], bool] | None = None,
    home: Path | None = None,
    repos: list[str] | None = None,
) -> dict[str, Any]:
    """Skip tickets whose detached child already died fail-closed / miss-N.

    Live pids are left alone. Dead pid + no PR + no classified reason is
    fail-closed (no_pr): a vanished child is not a silent retry. Product misses
    (plan_only / zero_diff / push_failed) count unique run_ids and only
    leave the slot after N; harvest does not CLOSE the issue. A stale
    blocked miss row below N is reconciled (reopened); crash rows stay buried.
    """
    home_root = Path(home) if home is not None else Path.home()
    default_cycle, isolated_home = _isolated_mill_roots(state_path, home_root)
    root = Path(cycle_dir) if cycle_dir is not None else default_cycle
    if home is None:
        home_root = isolated_home
    check = is_live or is_live_issue_to_pr_pid
    events, history = _index_issue_to_pr_log(state_path)
    if root.is_dir():
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
                receipt_reason = data.get("reason")
                if isinstance(receipt_reason, str) and receipt_reason in FAIL_CLOSED:
                    reason = receipt_reason
                    event = event or {"ok": False, "reason": reason}
            if not reason:
                receipt_pr = _as_int(data.get("pr"))
                event_pr = _as_int((event or {}).get("pr")) if event else None
                if receipt_pr or event_pr or _event_delivered(event):
                    # Delivery already happened. Drop a stale vanished row.
                    _clear_stale_no_pr(stuck, repo, issue)
                    continue
                # Vanished: dead child, no PR, no journal event.
                # An unknown ok=False is not no_pr.
                if event is not None:
                    continue
                reason = "no_pr"
                event = {
                    "ok": False,
                    "reason": "no_pr",
                    "error": "issue_to_pr produced no PR",
                }
            error = ""
            if event:
                error = str(event.get("error") or event.get("reason") or reason)

            if reason in FAIL_CLOSED:
                # Crash / red-recheck stays buried. Do not increment a corpse.
                if is_blocked_in_ledger(stuck, repo, issue):
                    continue
                row = record_failure(
                    stuck,
                    repo=repo,
                    number=issue,
                    error=error or reason,
                    max_failures=1,
                )
                row["blocked"] = True
                row["reason"] = reason
                continue

            if reason not in MISS_REASONS:
                continue
            miss_reason, miss_runs = _trailing_miss_runs(
                history.get((repo, issue)) or []
            )
            counted = miss_reason or reason
            # Journal fallback has no run history; treat as a single miss.
            if miss_runs == 0:
                miss_runs = 1
                counted = reason
            # Reconcile even when the ledger already says blocked: a 1-shot
            # plan_only/zero_diff/push_failed row is stale vs unique-run N.
            _apply_miss_count(
                stuck,
                repo=repo,
                issue=issue,
                reason=counted,
                miss_runs=miss_runs,
                error=error or counted,
            )

    # Receipts can be pruned and stuck.json can be overwritten mid-pass.
    # Re-apply terminal plan_only from the journal so the mill cannot loop
    # the same ticket after a wipe.
    for (repo, issue), hist in history.items():
        miss_reason, miss_runs = _trailing_miss_runs(hist)
        if miss_reason != "plan_only" or miss_runs < _skip_after("plan_only"):
            continue
        ev = events.get((repo, issue)) or {}
        _apply_miss_count(
            stuck,
            repo=repo,
            issue=issue,
            reason="plan_only",
            miss_runs=miss_runs,
            error=str(ev.get("error") or ev.get("reason") or "plan_only"),
        )

    # Receipts can be pruned. A later issue_closed / ok=True event must still
    # drop a vanished no_pr corpse so save_stuck cannot restore it.
    for (repo, issue), event in events.items():
        if _event_delivered(event):
            _clear_stale_no_pr(stuck, repo, issue)

    # Receipts can be pruned. Reconcile stale blocked miss rows from the
    # journal so unique-run N still owns the slot.
    for key, row in list((stuck.get("issues") or {}).items()):
        if not isinstance(row, dict) or not row.get("blocked"):
            continue
        if str(row.get("reason") or "") not in MISS_REASONS:
            continue
        repo, sep, num_s = str(key).rpartition("#")
        issue = _as_int(num_s)
        if not sep or not repo or issue is None:
            continue
        miss_reason, miss_runs = _trailing_miss_runs(
            history.get((repo, issue)) or []
        )
        if miss_runs == 0:
            continue
        counted = miss_reason or str(row.get("reason"))
        _apply_miss_count(
            stuck,
            repo=repo,
            issue=issue,
            reason=counted,
            miss_runs=miss_runs,
            error=str(row.get("last_error") or counted),
        )
    _clear_github_closed_mill_rows(stuck)
    _drop_out_of_scope_stuck_rows(stuck, repos)
    _clear_stale_cycle_start_receipts(root, repos=repos)
    return stuck
