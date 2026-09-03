"""Lift the first idle or cap sieve slot into the department nest receipt."""


def select(prepared: dict, rows: list[dict]) -> dict:
    chosen = None
    for row in rows:
        if row.get("route") in {"idle", "cap"}:
            chosen = row
            break
    if chosen is None:
        for row in reversed(rows):
            if row.get("route") == "continue":
                chosen = row
                break
    if chosen is None:
        last = prepared.get("last") if isinstance(prepared.get("last"), dict) else {}
        leftover_issues = list(last.get("leftover_issues") or [])
        leftover = int(last.get("leftover") or len(leftover_issues) or 0)
        spent = int(prepared.get("spent") or 0)
        chosen = {
            "ok": True,
            "route": "cap" if leftover > 0 else "idle",
            "spent": spent,
            "leftover": leftover,
            "leftover_issues": leftover_issues,
            "result": last,
        }
    result = dict(chosen.get("result") or {})
    result.update(
        launched=None,
        leftover=int(chosen.get("leftover") or result.get("leftover") or 0),
        leftover_issues=list(
            chosen.get("leftover_issues") or result.get("leftover_issues") or []
        ),
        rows=int(chosen.get("spent") or result.get("rows") or 0),
        spent=int(chosen.get("spent") or 0),
        budget=int(prepared.get("cap") or prepared.get("budget") or chosen.get("budget") or 0),
        stop=chosen.get("route"),
        department="issue_triage",
    )
    return {
        "ok": True,
        "route": str(chosen.get("route") or "idle"),
        "department": "issue_triage",
        "launched": None,
        "result": result,
    }
