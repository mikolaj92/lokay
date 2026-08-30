"""Authored leftover walk. Consume only on authored skip; else keep the row."""

from lokay.proc.classify_issue_assignee import mill_of, takeable
from lokay.proc.pass_lane import is_oil_repo, self_repo

CONSUME = frozenset(
    {
        "needs_human",
        "blocked",
        "already-closed",
        "already_closed",
        "issue_already_closed",
        "closed",
        "close",
    }
)
READY_LABELS = frozenset({"work:ready", "ai:ready"})


def identity(row: dict | None) -> tuple[str, int] | None:
    if not row or row.get("issue") is None:
        return None
    return (str(row.get("repo") or ""), int(row["issue"]))


def consumes(reason: object) -> bool:
    return str(reason or "") in CONSUME


def row_is_ready(row: dict | None) -> bool:
    if not isinstance(row, dict):
        return False
    labels = {str(item) for item in list(row.get("labels") or [])}
    return bool(labels & READY_LABELS)


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


def product_first(rows: list[dict] | None, *, self_id: str = "") -> list[dict]:
    """Product wins. Lokay oil is not the product slot while product remains."""
    listed = [dict(row) for row in list(rows or []) if isinstance(row, dict)]
    owner = self_id or self_repo()
    product = [
        row
        for row in listed
        if not is_oil_repo(str(row.get("repo") or ""), self_id=owner)
    ]
    return product or listed


def ownable(rows: list[dict] | None, mill: str) -> list[dict]:
    """Drop rows that already have someone other than the mill."""
    return [row for row in list(rows or []) if takeable(row, mill)]


def unoccupied(rows: list[dict] | None, occupied=None) -> list[dict]:
    """Drop rows whose repo already has a live issue_to_pr receipt."""
    blocked = {str(name) for name in list(occupied or []) if name}
    listed = [dict(row) for row in list(rows or []) if isinstance(row, dict)]
    if not blocked:
        return listed
    return [row for row in listed if str(row.get("repo") or "") not in blocked]


def queue(
    listed_rows: list | None,
    last: dict | None,
    *,
    mill: str = "",
    occupied=None,
) -> list[dict]:
    """Leftover listed issues stay the queue. Oil yields to live product.

    Foreign-owned rows (anyone besides the mill) are not the consumption
    queue. They stay on the listed page; selection walks past them.
    A live receipt occupies its repo the same way: leftover walks past it.
    """
    last = last if isinstance(last, dict) else {}
    mill_login = mill or mill_of(last)
    leftover = [
        row for row in list(last.get("leftover_issues") or []) if isinstance(row, dict)
    ]
    live_rows = [dict(row) for row in list(listed_rows or []) if identity(row)]
    live = {identity(row): row for row in live_rows}
    if leftover:
        kept = [live[key] for row in leftover if (key := identity(row)) in live]
        product = product_first(kept)
        candidates = product if product else (product_first(live_rows) or kept)
        return unoccupied(ownable(candidates, mill_login), occupied)
    return unoccupied(
        ownable(product_first(after(listed_rows, last) or live_rows), mill_login),
        occupied,
    )
