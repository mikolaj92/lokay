"""Lift the first idle or cap executor slot into the department nest receipt."""

from lokay.proc.classify_issue_row import launched_of


def select(prepared: dict, rows: list[dict]) -> dict:
    chosen = None
    launched = None
    for row in rows:
        if launched_of(row):
            launched = "started"
        if chosen is None and row.get("route") in {"idle", "cap"}:
            chosen = row
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
    launched = launched or (
        "started" if launched_of({"result": result}) else result.get("launched")
    )
    result.update(
        launched=launched,
        leftover=int(chosen.get("leftover") or result.get("leftover") or 0),
        leftover_issues=list(
            chosen.get("leftover_issues") or result.get("leftover_issues") or []
        ),
        rows=int(chosen.get("slot") or chosen.get("spent") or result.get("rows") or 0),
        spent=int(chosen.get("spent") or 0),
        budget=int(prepared.get("cap") or prepared.get("budget") or chosen.get("budget") or 0),
        stop=chosen.get("route"),
        department="executor",
    )
    return {
        "ok": True,
        "route": str(chosen.get("route") or "idle"),
        "department": "executor",
        "result": result,
    }
