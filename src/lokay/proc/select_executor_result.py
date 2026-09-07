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
        leftover_issues = list(
            prepared.get("leftover_issues")
            if "leftover_issues" in prepared
            else last.get("leftover_issues")
            or []
        )
        leftover = int(
            prepared.get("leftover")
            if "leftover" in prepared
            else last.get("leftover")
            or len(leftover_issues)
            or 0
        )
        spent = int(prepared.get("spent") or 0)
        chosen = {
            "ok": True,
            "route": "cap" if leftover > 0 or spent > 0 else "idle",
            "spent": spent,
            "leftover": leftover,
            "result": last,
        }
        # Cap/empty slots never ran select_next_issue — keep prepared fuel (#1071).
        if leftover_issues:
            chosen["leftover_issues"] = leftover_issues
        elif "leftover_issues" in prepared:
            chosen["leftover_issues"] = []
    result = dict(chosen.get("result") or {})
    launched = launched or (
        "started" if launched_of({"result": result}) else result.get("launched")
    )
    leftover_issues = list(
        chosen.get("leftover_issues")
        if "leftover_issues" in chosen
        else result.get("leftover_issues")
        if "leftover_issues" in result
        else prepared.get("leftover_issues")
        if "leftover_issues" in prepared
        else []
    )
    leftover = int(
        chosen.get("leftover")
        if chosen.get("leftover") is not None
        else result.get("leftover")
        if result.get("leftover") is not None
        else prepared.get("leftover")
        or len(leftover_issues)
        or 0
    )
    result.update(
        launched=launched,
        leftover=leftover,
        rows=int(chosen.get("slot") or chosen.get("spent") or result.get("rows") or 0),
        spent=int(chosen.get("spent") or 0),
        budget=int(prepared.get("cap") or prepared.get("budget") or chosen.get("budget") or 0),
        stop=chosen.get("route"),
        department="executor",
    )
    # Do not force leftover_issues=[] — omit so record_pass can keep prior (#1067).
    if leftover_issues:
        result["leftover_issues"] = leftover_issues
    else:
        result.pop("leftover_issues", None)
    return {
        "ok": True,
        "route": str(chosen.get("route") or "idle"),
        "department": "executor",
        "result": result,
    }
