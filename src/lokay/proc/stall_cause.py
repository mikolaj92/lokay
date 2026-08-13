"""One job: print the most specific stall cause from last-pass.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

def default_path() -> Path:
    return Path.home() / ".lokay" / "last-pass.json"

# Most specific named field first. A truthy value anywhere in the receipt wins
# over later fields and over remaining-counter inference.
CAUSE_FIELDS: tuple[tuple[str, str], ...] = (
    ("pi_over_budget", "pi over budget"),
    ("plan_only_diff", "plan-only diff"),
    ("host_behind_origin_main", "host behind origin/main"),
    ("llm_review_blocked_merge", "llm review blocked merge"),
)

CAUSE_PHRASES: tuple[tuple[str, str], ...] = (
    ("pi over budget", "pi over budget"),
    ("over budget", "pi over budget"),
    ("plan-only diff", "plan-only diff"),
    ("plan only diff", "plan-only diff"),
    ("host behind origin/main", "host behind origin/main"),
    ("behind origin/main", "host behind origin/main"),
    ("llm review blocked merge", "llm review blocked merge"),
)

REASON_CAUSES: dict[str, str] = {
    "pi_over_budget": "pi over budget",
    "over_budget": "pi over budget",
    "plan_only_diff": "plan-only diff",
    "zero_diff": "plan-only diff",
    "host_behind_origin_main": "host behind origin/main",
    "host_behind": "host behind origin/main",
    "llm_review_blocked_merge": "llm review blocked merge",
    "llm_review_not_approved": "llm review blocked merge",
    "llm_review_missing": "llm review blocked merge",
    "llm_review_inconsistent": "llm review blocked merge",
    "llm_review_requires_executor": "llm review blocked merge",
    "llm_review_requested_changes": "llm review blocked merge",
    "llm_review_escalated_needs_review": "llm review blocked merge",
}

_TEXT_KEYS = frozenset(
    {"error", "note", "reason", "cause", "stall_cause", "message"}
)
_FALSEY_STRINGS = frozenset({"", "0", "false", "no", "off", "none", "null"})


def _truthy(value: Any) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() not in _FALSEY_STRINGS
    if isinstance(value, (dict, list, tuple, set)):
        return bool(value)
    return bool(value)


def _any_truthy(obj: Any, key: str) -> bool:
    if isinstance(obj, dict):
        if key in obj and _truthy(obj[key]):
            return True
        return any(_any_truthy(item, key) for item in obj.values())
    if isinstance(obj, list):
        return any(_any_truthy(item, key) for item in obj)
    return False


def _collect_texts(obj: Any, into: list[str]) -> None:
    if isinstance(obj, dict):
        for key, item in obj.items():
            if key in _TEXT_KEYS:
                if isinstance(item, str) and item.strip():
                    into.append(item)
                elif isinstance(item, dict):
                    _collect_texts(item, into)
            elif isinstance(item, (dict, list)):
                _collect_texts(item, into)
    elif isinstance(obj, list):
        for item in obj:
            _collect_texts(item, into)


def _collect_reasons(obj: Any, into: list[str]) -> None:
    if isinstance(obj, dict):
        raw = obj.get("reason")
        if isinstance(raw, str) and raw.strip():
            into.append(raw.strip())
        for item in obj.values():
            if isinstance(item, (dict, list)):
                _collect_reasons(item, into)
    elif isinstance(obj, list):
        for item in obj:
            _collect_reasons(item, into)


def _remaining(data: dict[str, Any]) -> dict[str, Any]:
    rem = data.get("remaining")
    return rem if isinstance(rem, dict) else {}


def _count(rem: dict[str, Any], key: str) -> int:
    try:
        return int(rem.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _error_text(data: dict[str, Any]) -> str | None:
    error = data.get("error")
    if isinstance(error, str) and error.strip():
        return error.strip()
    if isinstance(error, dict):
        for key in ("message", "error", "reason"):
            raw = error.get(key)
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
    note = data.get("note")
    if isinstance(note, str) and note.strip():
        return note.strip()
    return None


def cause_line(data: dict[str, Any]) -> str:
    """Return one operator-facing cause. Most specific field wins."""
    ranked = {label: index for index, (_, label) in enumerate(CAUSE_FIELDS)}
    hits: list[tuple[int, str]] = []
    for key, label in CAUSE_FIELDS:
        if _any_truthy(data, key):
            hits.append((ranked[label], label))

    reasons: list[str] = []
    _collect_reasons(data, reasons)
    for reason in reasons:
        label = REASON_CAUSES.get(reason)
        if label is not None:
            hits.append((ranked.get(label, len(CAUSE_FIELDS)), label))

    texts: list[str] = []
    _collect_texts(data, texts)
    blob = " ".join(texts).lower()
    for needle, label in CAUSE_PHRASES:
        if needle in blob:
            hits.append((ranked[label], label))

    if hits:
        hits.sort()
        return hits[0][1]

    rem = _remaining(data)
    require_llm = data.get("require_llm_review")
    if require_llm is None:
        require_llm = True
    merge_enabled = data.get("merge_enabled")
    if merge_enabled is None:
        merge_enabled = True
    if _truthy(require_llm) and _truthy(merge_enabled) and _count(rem, "review_limbo") > 0:
        return "llm review blocked merge"

    if _count(rem, "survey_errors") > 0:
        return "survey error"
    if _count(rem, "merge_conflicts") > 0:
        return "merge conflicts"
    if _count(rem, "needs_repair") > 0:
        return "needs repair"
    if _count(rem, "pending_checks") > 0:
        return "pending checks"
    if _count(rem, "no_checks_blocked") > 0:
        return "no checks blocked"
    if _count(rem, "merge_disabled") > 0 or (
        not _truthy(merge_enabled) and _count(rem, "mergeable_green") > 0
    ):
        return "merge disabled"

    generic = _error_text(data)
    if generic:
        return generic
    health = data.get("health")
    if isinstance(health, str) and health.strip():
        return health.strip()
    return "unknown"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="stall_cause")
    parser.add_argument(
        "--file",
        help="last-pass JSON path (default: ~/.lokay/last-pass.json)",
    )
    args = parser.parse_args(argv)
    path = Path(str(args.file)).expanduser() if args.file else default_path()
    if not path.is_file():
        sys.stderr.write("missing last-pass json\n")
        return 2
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        sys.stderr.write("unreadable last-pass json\n")
        return 1
    if not isinstance(data, dict):
        sys.stderr.write("unreadable last-pass json\n")
        return 1
    sys.stdout.write(cause_line(data) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
