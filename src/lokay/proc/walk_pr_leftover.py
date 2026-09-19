"""Authored leftover walk for the PR sieve. Skip without merge consumes the SHA."""

KEEP_REASONS = frozenset(
    {
        "checks_pending",
        "checks_offline",
        "checks_none_require_checks",
        "checks_missing",
        "ci_repair_start_head_missing",
        "merge_disabled",
        "repair_push_recovered",
    }
)
KEEP_ROUTES = frozenset({"wait"})
KEEP_VERDICTS = frozenset({"repair"})
_PLUGIN_INCOMPLETE = frozenset(
    {
        "plugin_error",
        "review_plugin_failed",
        "review_failed_closed",
        "review_result_invalid",
        "review_request_missing",
    }
)
OCCUPANCY_SCHEMA = {
    "type": "object",
    "required": ["class", "keep"],
    "additionalProperties": False,
    "properties": {
        "class": {
            "type": "string",
            "enum": [
                "incomplete",
                "complete_reject",
                "merge",
                "pending",
                "repair",
                "consumed",
            ],
        },
        "keep": {"type": "boolean"},
    },
    "oneOf": [
        {"properties": {"class": {"const": "incomplete"}, "keep": {"const": True}}},
        {"properties": {"class": {"const": "complete_reject"}, "keep": {"const": False}}},
        {"properties": {"class": {"const": "merge"}, "keep": {"const": False}}},
        {"properties": {"class": {"const": "pending"}, "keep": {"const": True}}},
        {"properties": {"class": {"const": "repair"}, "keep": {"const": True}}},
        {"properties": {"class": {"const": "consumed"}, "keep": {"const": False}}},
    ],
}


def identity(row: dict | None) -> tuple[str, int, str] | None:
    if not row or row.get("pr") is None:
        return None
    try:
        number = int(row["pr"])
    except (TypeError, ValueError):
        return None
    return (str(row.get("repo") or ""), number, str(row.get("head_sha") or ""))


def skipped_identity(last: dict | None) -> tuple[str, int, str] | None:
    if not isinstance(last, dict) or last.get("skipped_pr") is None:
        return None
    try:
        number = int(last["skipped_pr"])
    except (TypeError, ValueError):
        return None
    return (
        str(last.get("skipped_repo") or ""),
        number,
        str(last.get("skipped_head_sha") or ""),
    )


def _reason_code(reason: str) -> str:
    return reason.split(":", 1)[0].strip()


_COMPLETE_REJECT_DETAILS = frozenset({"review has warnings"})


def incomplete_review(reason: str) -> bool:
    """True when OCR/plugin produced no complete review JSON."""
    code = _reason_code(reason)
    detail = reason.split(":", 1)[1].strip() if ":" in reason else ""
    if code == "ocr_contract_rejected":
        return detail not in _COMPLETE_REJECT_DETAILS
    if code.startswith("ocr_"):
        return True
    return code in _PLUGIN_INCOMPLETE


def classify_occupancy(receipt: object) -> dict:
    """Leftover occupancy: incomplete JSON KEEP; complete reject consume."""
    if not isinstance(receipt, dict):
        return {"class": "pending", "keep": True}
    if str(receipt.get("outcome") or "") == "merge" or str(receipt.get("verdict") or "") == "merge":
        return {"class": "merge", "keep": False}
    route = str(receipt.get("route") or "")
    reason = str(receipt.get("reason") or "")
    verdict = str(receipt.get("verdict") or "")
    if route in KEEP_ROUTES or reason in KEEP_REASONS:
        return {"class": "pending", "keep": True}
    if verdict in KEEP_VERDICTS or receipt.get("repairable"):
        return {"class": "repair", "keep": True}
    if incomplete_review(reason):
        return {"class": "incomplete", "keep": True}
    if _reason_code(reason) == "ocr_contract_rejected":
        detail = reason.split(":", 1)[1].strip() if ":" in reason else ""
        if detail in _COMPLETE_REJECT_DETAILS:
            return {"class": "complete_reject", "keep": False}
    if route in {"fail_closed", "skip"} or (route == "completed" and verdict == "feedback"):
        return {"class": "consumed", "keep": False}
    return {"class": "pending", "keep": True}


def consumes(receipt: object) -> bool:
    """Skip / fail_closed / merge consume. Incomplete JSON and pending KEEP."""
    return not bool(classify_occupancy(receipt).get("keep"))


def after(rows: list | None, skipped: dict | None) -> list[dict]:
    """Listed rows after the skipped identity. Empty when the list is exhausted."""
    listed = [dict(row) for row in list(rows or []) if isinstance(row, dict)]
    key = identity(skipped)
    if key is None:
        return listed
    seen = False
    leftover: list[dict] = []
    for row in listed:
        if not seen:
            if identity(row) == key:
                seen = True
            continue
        leftover.append(row)
    return leftover if seen else listed


def keep(rows: list | None, picked: dict | None) -> list[dict]:
    """Listed rows from the pick inclusive. Empty only when exhausted."""
    listed = [dict(row) for row in list(rows or []) if isinstance(row, dict)]
    key = identity(picked)
    if key is None:
        return listed
    leftover: list[dict] = []
    seen = False
    for row in listed:
        if not seen:
            if identity(row) == key:
                seen = True
            else:
                continue
        leftover.append(row)
    return leftover if seen else listed


def leftover_after(picked: dict | None, receipt: dict | None) -> list[dict]:
    """Consume drops the pick. Incomplete JSON and pending KEEP start at the pick."""
    picked = picked if isinstance(picked, dict) else {}
    rest = [
        dict(row)
        for row in list(picked.get("leftover_prs") or [])
        if isinstance(row, dict)
    ]
    if consumes(receipt):
        return rest
    head = {
        key: picked.get(key)
        for key in ("repo", "pr", "title", "branch", "head_sha")
        if picked.get(key) is not None
    }
    if head.get("repo") is not None and head.get("pr") is not None:
        return [head, *rest]
    return rest


def _new_sha_of_skipped(row: dict, skipped: tuple[str, int, str] | None) -> bool:
    key = identity(row)
    if key is None or skipped is None:
        return False
    return key != skipped and key[0] == skipped[0] and key[1] == skipped[1]


def queue(listed_rows: list | None, last: dict | None) -> list[dict]:
    """Live open PRs minus a consumed (repo, pr, sha). New SHA is a new identity."""
    last = last if isinstance(last, dict) else {}
    live_rows = [dict(row) for row in list(listed_rows or []) if identity(row)]
    live = {identity(row): row for row in live_rows}
    leftover = [
        row for row in list(last.get("leftover_prs") or []) if isinstance(row, dict)
    ]
    skipped = skipped_identity(last)
    new_sha = [row for row in live_rows if _new_sha_of_skipped(row, skipped)]
    if leftover:
        leftover_ids = {identity(row) for row in leftover if identity(row)}
        kept = [live[key] for row in leftover if (key := identity(row)) in live]
        extra = [
            row
            for row in live_rows
            if identity(row) not in leftover_ids
            and identity(row) != skipped
            and not _new_sha_of_skipped(row, skipped)
        ]
        return new_sha + kept + extra
    if skipped is not None:
        rest = [row for row in live_rows if identity(row) != skipped]
        return new_sha + rest if new_sha else rest
    return live_rows
