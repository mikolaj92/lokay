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


def consumes(receipt: object) -> bool:
    """Skip / fail_closed / merge consume. Pending checks KEEP the row."""
    if not isinstance(receipt, dict):
        return False
    if str(receipt.get("outcome") or "") == "merge":
        return True
    verdict = str(receipt.get("verdict") or "")
    if verdict == "merge":
        return True
    route = str(receipt.get("route") or "")
    reason = str(receipt.get("reason") or "")
    if route in KEEP_ROUTES:
        return False
    if reason in KEEP_REASONS:
        return False
    if verdict in KEEP_VERDICTS or receipt.get("repairable"):
        return False
    if route in {"fail_closed", "skip"}:
        return True
    if route == "completed" and verdict == "feedback":
        return True
    return False


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
    """Consume drops the pick. Pending KEEP starts at the pick."""
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
