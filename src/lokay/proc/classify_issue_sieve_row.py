"""Classify one authored sieve slot and persist the resume cursor."""

from lokay.proc.classify_issue_row import classify as classify_row
from lokay.proc.prepare_issue_sieve import write_cursor


def classify(selected: dict, row: dict, *, prepared: dict) -> dict:
    slot = int(selected.get("slot") or 0)
    if str(selected.get("route") or "") != "run":
        return {"ok": True, "route": "empty", "slot": slot}
    spent = int(prepared.get("spent") or 0) + slot
    budget = int(prepared.get("cap") or prepared.get("budget") or 0)
    decision = classify_row(
        row,
        spent=spent,
        budget=budget,
        bound_any=True,
    )
    inner = row.get("result") if isinstance(row.get("result"), dict) else row
    result = dict(inner or {})
    leftover_issues = list(
        decision.get("leftover_issues") or result.get("leftover_issues") or []
    )
    leftover = int(decision.get("leftover") or result.get("leftover") or 0)
    last = {
        **result,
        "launched": None,
        "leftover": leftover,
        "leftover_issues": leftover_issues,
    }
    write_cursor(
        str(prepared.get("pass_dir") or ""),
        {"last": last, "spent": spent, "route": decision.get("route")},
    )
    return {
        "ok": True,
        "route": str(decision.get("route") or "idle"),
        "slot": slot,
        "spent": spent,
        "budget": budget,
        "leftover": leftover,
        "leftover_issues": leftover_issues,
        "result": last,
        "department": "issue_triage",
        "launched": None,
    }
