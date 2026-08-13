"""Persistent 4-of-5 confirmation for repeated product-mill failures."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lokay.merge_policy import NEEDS_REVIEW_REASONS, WAITING_REASONS

_WINDOW = 5
_QUORUM = 4
_VOLATILE = re.compile(r"(?i)(?:0x)?[0-9a-f]{8,}|\b\d+\b")
_SPACE = re.compile(r"\s+")
# Honest wait / repair limbo must not confirm as mill failure for recovery.
_NON_FAILURE_HEALTH = frozenset(
    {"waiting", "repairing", "idle", "progress", "running", "offline", "overlap"}
)
# merge_policy / pr_triage soft product reasons — never systemic stall evidence.
# Keep aligned with WAITING_REASONS / NEEDS_REVIEW_REASONS; do not alter those sets.
_SOFT_PRODUCT_REASONS = frozenset(
    WAITING_REASONS
    | NEEDS_REVIEW_REASONS
    | {
        "checks_offline",
        "checks_missing",
        "checks_failed",
        "checks_not_mergeable",
        "llm_review_requested_changes",
        "llm_review_not_approved",
        "llm_review_missing",
        "llm_review_inconsistent",
        "llm_review_requires_executor",
        "executor_disabled",
        "pr_merge_skipped",
        "pr_review_skipped",
        "already_reviewed_head",
    }
)


def history_path_for(state_path: Path) -> Path:
    return state_path.with_name("recovery-history.json")


def normalize_failure(text: str) -> str:
    value = _SPACE.sub(" ", text).strip().lower()
    value = _VOLATILE.sub("<n>", value)
    return value[:1000]


_SOFT_REASON_NORMALIZED = frozenset(
    normalize_failure(reason) for reason in _SOFT_PRODUCT_REASONS
)


def _strings(value: Any, *, keys: frozenset[str]):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            if key in keys:
                yield from _strings(item, keys=keys)
            elif isinstance(item, (dict, list)):
                yield from _strings(item, keys=keys)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item, keys=keys)


def _delivered(row: dict[str, Any]) -> bool:
    if row.get("ok") is not True:
        return False
    terminal = row.get("terminal")
    if not isinstance(terminal, dict):
        return False
    if row.get("kind") == "issue_to_pr":
        created = terminal.get("pr_create")
        return isinstance(created, dict) and isinstance(created.get("pr"), dict)
    if row.get("kind") == "pr_triage":
        merged = terminal.get("pr_merge")
        return isinstance(merged, dict) and merged.get("merged") is True
    return False


def _soft_mill_health(mill: dict[str, Any]) -> bool:
    """True for honest wait / repair / idle outcomes — never systemic stall."""
    return str(mill.get("health") or "") in _NON_FAILURE_HEALTH


def _soft_product_outcome(row: dict[str, Any]) -> bool:
    """True for merge_policy waiting / repair / needs-review product waits."""
    if any(
        row.get(flag)
        for flag in ("waiting", "repairable", "needs_review", "escalated")
    ):
        return True
    if str(row.get("reason") or "") in _SOFT_PRODUCT_REASONS:
        return True
    policy = row.get("merge_policy")
    if isinstance(policy, dict):
        action = str(policy.get("action") or "")
        if action in {"waiting", "repair", "disabled"}:
            return True
        if policy.get("waiting") or policy.get("repairable") or policy.get("needs_review"):
            return True
        if str(policy.get("reason") or "") in _SOFT_PRODUCT_REASONS:
            return True
    terminal = row.get("terminal")
    if isinstance(terminal, dict):
        for key in ("pr_merge", "pr_review"):
            node = terminal.get(key)
            if isinstance(node, dict) and _soft_product_outcome(node):
                return True
    return False


def _failure_texts(row: dict[str, Any]):
    """Yield failure strings; omit soft merge_policy reasons from soft rows."""
    # Soft product outcomes may still carry a hard executor/stderr failure — keep
    # those, but never hash waiting/repair/needs-review reason tokens into quorum.
    if _soft_product_outcome(row):
        keys = frozenset({"error", "message", "stderr", "stderr_tail"})
    else:
        keys = frozenset({"error", "message", "reason", "stderr", "stderr_tail"})
    for raw in _strings(row, keys=keys):
        normalized = normalize_failure(raw)
        if not normalized or normalized in _SOFT_REASON_NORMALIZED:
            continue
        if str(raw).strip() in _SOFT_PRODUCT_REASONS:
            continue
        yield raw, normalized


def observe_run(*, state_path: Path, state_offset: int, mill: dict[str, Any]) -> dict[str, Any]:
    """Describe one run using only events appended while that run held mill.lock."""
    events: list[dict[str, Any]] = []
    try:
        with state_path.open("r", encoding="utf-8") as handle:
            handle.seek(state_offset)
            for line in handle:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    events.append(row)
    except OSError:
        pass

    delivered = any(_delivered(row) for row in events)
    # Soft product outcomes (waiting / repairing / review limbo / pending CI /
    # parked needs-review → waiting/idle) must not mint recovery fingerprints
    # from either the mill envelope or per-event repair/triage failures.
    # Those cycles belong to the product mill, not self-repair.
    remaining = mill.get("remaining") if isinstance(mill.get("remaining"), dict) else {}
    detached_started = int(remaining.get("issue_to_pr_started") or 0)
    if delivered or _soft_mill_health(mill) or detached_started > 0:
        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "fingerprint": None,
            "evidence": "",
            "delivered": delivered,
            "health": mill.get("health") if detached_started == 0 else (
                mill.get("health") or "running"
            ),
            "progress": max(int(mill.get("progress") or 0), detached_started),
        }

    failures: list[str] = []
    evidence: dict[str, str] = {}
    for row in events:
        if row.get("ok") is not False:
            continue
        for raw, normalized in _failure_texts(row):
            fingerprint = hashlib.sha256(normalized.encode()).hexdigest()[:16]
            failures.append(fingerprint)
            evidence.setdefault(fingerprint, raw[:4000])
    # True carrier/preflight/product-mill failures only: envelope fallback when
    # no event text was available and health is not an honest soft wait.
    if not failures and not mill.get("ok"):
        raw = str(mill.get("error") or mill.get("health") or "mill failed")
        # Soft-looking mill errors must not confirm either.
        if (
            normalize_failure(raw) in _SOFT_REASON_NORMALIZED
            or str(raw).strip() in _SOFT_PRODUCT_REASONS
            or str(raw).strip() in _NON_FAILURE_HEALTH
        ):
            return {
                "ts": datetime.now(timezone.utc).isoformat(),
                "fingerprint": None,
                "evidence": "",
                "delivered": False,
                "health": mill.get("health"),
                "progress": int(mill.get("progress") or 0),
            }
        normalized = normalize_failure(raw)
        fingerprint = hashlib.sha256(normalized.encode()).hexdigest()[:16]
        failures.append(fingerprint)
        evidence[fingerprint] = raw
    dominant = Counter(failures).most_common(1)[0][0] if failures else None
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "fingerprint": dominant,
        "evidence": "" if dominant is None else evidence[dominant],
        "delivered": False,
        "health": mill.get("health"),
        "progress": int(mill.get("progress") or 0),
    }


def record_observation(path: Path, observation: dict[str, Any]) -> dict[str, Any] | None:
    """Append an observation and return a confirmed signal at 4 matching of 5.

    Soft waiting/repairing rows may occupy the rolling window (diluting quorum)
    but never count as matching failure fingerprints.
    """
    rows: list[dict[str, Any]] = []
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, list):
            rows = [row for row in loaded if isinstance(row, dict)]
    except (OSError, ValueError):
        pass
    stored = dict(observation)
    # Defense in depth: soft mill health cannot fill quorum even if a caller
    # stamped a fingerprint by mistake.
    if str(stored.get("health") or "") in _NON_FAILURE_HEALTH:
        stored["fingerprint"] = None
        stored["evidence"] = ""
    rows = [*rows, stored][-_WINDOW:]
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(rows, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    tmp.replace(path)

    fingerprint = stored.get("fingerprint")
    if not fingerprint:
        return None
    matches = [
        row
        for row in rows
        if row.get("fingerprint") == fingerprint
        and str(row.get("health") or "") not in _NON_FAILURE_HEALTH
    ]
    if len(rows) < _WINDOW or len(matches) < _QUORUM:
        return None
    evidence = next((str(row.get("evidence") or "") for row in reversed(matches)), "")
    return {
        "fingerprint": fingerprint,
        "matches": len(matches),
        "window": len(rows),
        "evidence": evidence,
        "health": "confirmed_stall",
    }
