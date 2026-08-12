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


def receipt_path_for(state_path: Path | None = None) -> Path:
    if state_path is not None:
        return Path(state_path).expanduser().resolve().parent / RECEIPT_NAME
    return Path.home() / ".lokay" / RECEIPT_NAME


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
    }


def write_pass_receipt(
    receipt: dict[str, Any],
    *,
    state_path: Path | None = None,
    path: Path | None = None,
) -> Path:
    """Atomically write receipt JSON. Returns the path written."""
    target = path or receipt_path_for(state_path)
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
