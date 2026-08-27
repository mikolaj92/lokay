"""Authored leftover walk. Two small functions: after skip, then the queue."""


def identity(row: dict | None) -> tuple[str, int] | None:
    if not row or row.get("issue") is None:
        return None
    return (str(row.get("repo") or ""), int(row["issue"]))


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


def queue(listed_rows: list | None, last: dict | None) -> list[dict]:
    """Leftover listed issues stay the queue. Else walk after the last skip."""
    last = last if isinstance(last, dict) else {}
    leftover = [row for row in list(last.get("leftover_issues") or []) if isinstance(row, dict)]
    live = {identity(row): dict(row) for row in list(listed_rows or []) if identity(row)}
    if leftover:
        return [live[key] for row in leftover if (key := identity(row)) in live]
    return after(listed_rows, last)
