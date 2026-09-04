"""Compact factory-pass receipt for LaunchAgent / operator logs.

Written under the config state directory (default ``~/.lokay/last-pass.json``)
by ``lokay-record-pass`` after each factory pass that produces a real remaining
survey. Small, structured JSON — not a second execution ledger.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RECEIPT_NAME = "last-pass.json"
_TOY_REPOS = frozenset({"o/r", "a/three", "a/clean", "a/two", "a/four", "a/b"})
_FIXTURE_CONFIG_MARKERS = (
    "pytest-of-",
    "/pytest/",
    "/private/var/folders/",
    "/tmp/pytest",
    "pytest-cache",
)
_PRODUCT_HEALTH = frozenset({"progress", "idle", "overlap", "repairing", "waiting"})


def lokay_receipt_path() -> Path:
    return Path.home() / ".lokay" / RECEIPT_NAME


def receipt_path_for(state_path: Path | None = None) -> Path:
    if state_path is not None:
        return Path(state_path).expanduser().resolve().parent / RECEIPT_NAME
    return lokay_receipt_path()


def _remaining_of(receipt: dict[str, Any]) -> dict[str, Any]:
    rem = receipt.get("remaining")
    return rem if isinstance(rem, dict) else {}


def _repos_of(receipt: dict[str, Any]) -> list[str]:
    rem = _remaining_of(receipt)
    rows = rem.get("by_repo") or receipt.get("by_repo") or []
    out: list[str] = []
    for row in rows:
        if isinstance(row, dict) and row.get("repo"):
            out.append(str(row["repo"]))
    return out


def incoming_is_fixture(receipt: dict[str, Any]) -> bool:
    """True when this receipt came from pytest / toy catalog, not the lokay."""
    config = str(receipt.get("config") or "").replace("\\", "/").lower()
    if any(marker in config for marker in _FIXTURE_CONFIG_MARKERS):
        return True
    repos = _repos_of(receipt)
    return bool(repos) and all(repo in _TOY_REPOS or repo.startswith("a/") for repo in repos)


def existing_is_product(receipt: dict[str, Any]) -> bool:
    """True when on-disk last-pass looks like a live lokay glance."""
    if receipt.get("kind") != "pass_receipt":
        return False
    rem = _remaining_of(receipt)
    work = (
        int(rem.get("ready") or 0)
        + int(rem.get("issue_to_pr_started") or 0)
        + int(rem.get("open_ai_prs") or 0)
    )
    repos = _repos_of(receipt)
    real = any(
        repo not in _TOY_REPOS and "/" in repo and not repo.startswith("a/")
        for repo in repos
    )
    liveish = bool(receipt.get("live")) or receipt.get("health") in _PRODUCT_HEALTH
    return work > 0 and real and liveish


def _should_skip_clobber(target: Path, receipt: dict[str, Any]) -> bool:
    if not incoming_is_fixture(receipt):
        return False
    try:
        resolved = target.expanduser().resolve()
    except OSError:
        resolved = target
    if resolved == lokay_receipt_path().resolve():
        return True
    existing = read_pass_receipt(path=target)
    return bool(existing) and existing_is_product(existing)


def _receipt_new_pr(tick: dict[str, Any]) -> bool:
    if tick.get("new_pr") is True:
        return True
    remaining = tick.get("remaining") if isinstance(tick.get("remaining"), dict) else {}
    if remaining.get("new_pr") or remaining.get("pr_created"):
        return True
    for action in list(tick.get("actions") or []):
        if not isinstance(action, dict):
            continue
        step = str(action.get("step") or "")
        if step == "pr_create":
            return True
        if step == "issue_to_pr" and (
            action.get("pr") or action.get("pr_number") or action.get("url")
        ):
            return True
    return False


def _receipt_merged(tick: dict[str, Any]) -> bool:
    if tick.get("merged") is True:
        return True
    merged = tick.get("merged_this_pass")
    if merged is True or (isinstance(merged, list) and merged):
        return True
    remaining = tick.get("remaining") if isinstance(tick.get("remaining"), dict) else {}
    nested = remaining.get("merged_this_pass")
    if nested is True or (isinstance(nested, list) and nested):
        return True
    for action in list(tick.get("actions") or []):
        if not isinstance(action, dict):
            continue
        if action.get("merged") is True:
            return True
        if str(action.get("step") or "") == "pr_merge" and action.get("merged"):
            return True
    return False


def _receipt_leftover_skip(tick: dict[str, Any]) -> bool:
    if tick.get("leftover_skip") is True:
        return True
    if str(tick.get("reason") or "") == "leftover_overflow":
        return True
    leftover = tick.get("leftover_closeout")
    if isinstance(leftover, dict) and (
        leftover.get("leftover_skip")
        or leftover.get("reason") == "leftover_overflow"
        or (leftover.get("skipped") and "leftover" in str(leftover.get("reason") or ""))
    ):
        return True
    blob = str(tick.get("error") or "").lower()
    return "leftover_overflow" in blob or "leftover closeout catalog exceeds" in blob


def build_pass_receipt(
    *,
    tick: dict[str, Any],
    merge_enabled: bool,
    max_issue_to_pr_per_pass: int,
    config_path: str | None = None,
    require_checks: bool = False,
    require_llm_review: bool = True,
) -> dict[str, Any]:
    """Build a compact receipt from a tick/status survey payload."""
    remaining = tick.get("remaining") if isinstance(tick.get("remaining"), dict) else {}
    # Drop bulky action logs; keep operator-facing counters + per-repo rows.
    compact_remaining = {
        k: remaining[k]
        for k in (
            "inbox",
            "ready",
            "ready_with_open_pr",
            "open_ai_prs",
            "actionable_open_ai_prs",
            "manual_open_ai_prs",
            "mergeable_green",
            "merge_disabled",
            "needs_repair",
            "review_limbo",
            "pending_checks",
            "no_checks_blocked",
            "merge_conflicts",
            "survey_errors",
            "issue_to_pr_started",
            "max_issue_to_pr_per_pass",
            "by_repo",
        )
        if k in remaining
    }
    human = tick.get("human_residuals")
    if not isinstance(human, dict):
        human = {"count": int(remaining.get("human_residuals") or 0)}
    return {
        "kind": "pass_receipt",
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "config": config_path,
        "ok": bool(tick.get("ok")),
        "health": tick.get("health"),
        "idle": tick.get("idle"),
        "live": tick.get("live"),
        "progress": int(tick.get("progress") or 0),
        # Pass receipt preserves survey probe uncertainty.
        "probe_failed": bool(tick.get("probe_failed")),
        "merge_enabled": bool(merge_enabled),
        "require_checks": bool(require_checks),
        "require_llm_review": bool(require_llm_review),
        "max_issue_to_pr_per_pass": int(max_issue_to_pr_per_pass),
        "remaining": compact_remaining,
        "by_repo": list(remaining.get("by_repo") or tick.get("by_repo") or []),
        "human_residuals": {
            "count": int(human.get("count") or 0),
            "note": human.get("note")
            or "see lokay status --human for residual mailbox detail",
        },
        "error": tick.get("error"),
        "note": tick.get("note"),
        "lane": str(tick.get("lane") or "idle"),
        "new_pr": _receipt_new_pr(tick),
        "merged": _receipt_merged(tick),
        "leftover_skip": _receipt_leftover_skip(tick),
        "reason": tick.get("reason"),
    }


def write_pass_receipt(
    receipt: dict[str, Any],
    *,
    state_path: Path | None = None,
    path: Path | None = None,
) -> Path:
    """Atomically write receipt JSON. Returns the path written.

    Fixture receipts (pytest tmp config, toy ``o/r`` catalog) must not clobber
    the lokay glance file at ``~/.lokay/last-pass.json``. Isolated ``state_path``
    writes still land next to the test state.
    """
    target = path or receipt_path_for(state_path)
    if _should_skip_clobber(target, receipt):
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(
        json.dumps(receipt, ensure_ascii=False, default=str, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp.replace(target)
    return target


def read_pass_receipt(*, state_path: Path | None = None, path: Path | None = None) -> dict[str, Any] | None:
    target = path or receipt_path_for(state_path)
    if not target.is_file():
        return None
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None
