"""Pick one listed issue. Labeled start only; unlabeled is never fuel."""

import os

from lokay.proc.classify_issue_assignee import lokay_of, takeable
from lokay.proc.classify_open_issues import classify
from lokay.proc.pick_one_labeled import READY_LABELS
from lokay.proc.walk_issue_leftover import identity, queue, row_is_ready


def occupied_repos_of(occupied=None) -> set[str]:
    """Live receipts occupy a repo. Pytest stays empty unless the test passes a set."""
    if occupied is not None:
        return {str(name) for name in occupied if name}
    from lokay.proc.issue_delivery_occupancy import live_issue_to_pr_receipts

    return {
        str(row.get("repo") or "")
        for row in live_issue_to_pr_receipts()
        if row.get("repo")
    }


def _label_names(row: dict) -> list[str]:
    names: list[str] = []
    for item in list(row.get("labels") or []):
        if isinstance(item, dict):
            name = str(item.get("name") or "")
        else:
            name = str(item or "")
        if name:
            names.append(name)
    return names


def _admit_sieve_do(rows: list) -> list[dict]:
    """Sieve do is this pass's ready stamp. Do not re-list GitHub to see it."""
    admitted: list[dict] = []
    for raw in rows:
        row = dict(raw)
        decision = row.get("sieve_decision") or {}
        if isinstance(decision, dict) and decision.get("route") == "do":
            labels = _label_names(row)
            if not (set(labels) & READY_LABELS):
                labels.append("ai:ready")
            row["labels"] = labels
        admitted.append(row)
    return admitted


def _none(*, reason: str) -> dict:
    # leftover:0 without leftover_issues=[] lets record_pass keep prior fuel (#1067).
    return {"ok": True, "route": "none", "reason": reason, "leftover": 0}


def pick(classified: dict) -> dict:
    if classified.get("route") != "listed":
        return {
            "ok": True,
            "route": "none",
            "reason": classified.get("reason") or "skip",
        }
    rows = list(classified.get("issues") or [])
    if not rows:
        return {"ok": True, "route": "none", "reason": "no_open_issue"}
    leftover = max(0, len(rows) - 1)
    row = dict(rows[0])
    return {
        **row,
        "ok": True,
        "route": "ready" if row_is_ready(row) else "issue",
        "leftover": leftover,
        "leftover_issues": [dict(item) for item in rows[1:]],
    }


def select(listed: dict, last: dict | None = None, occupied=None) -> dict:
    classified = classify(listed)
    if classified.get("route") != "listed":
        return pick(classified)
    lokay = lokay_of(listed, last)
    occupied_repos = occupied_repos_of(occupied)
    from lokay.proc.pick_one_labeled import pick_one_labeled

    listed_rows = _admit_sieve_do(list(classified.get("issues") or []))
    candidates = queue(listed_rows, last, lokay=lokay, occupied=occupied_repos)
    labeled = pick_one_labeled(candidates)
    if labeled["reason"] == "picked":
        chosen = dict(labeled["issue"])
        rest = [
            dict(row)
            for row in candidates
            if row is not labeled["issue"]
        ]
        return pick({"route": "listed", "issues": [chosen, *rest]})
    if labeled["reason"] == "occupied":
        return _none(reason="occupied")
    takeable_rows = [row for row in listed_rows if takeable(row, lokay)]
    if listed_rows and not takeable_rows:
        return _none(reason="foreign_assignee")
    if takeable_rows and occupied_repos and all(
        str(row.get("repo") or "") in occupied_repos for row in takeable_rows
    ):
        return _none(reason="occupied")
    # A listed, takeable, unoccupied issue is the work. No label is required.
    if takeable_rows:
        # Honor the last pass's leftover cursor so a consumed skip moves the queue on.
        cursor = {identity(row) for row in list((last or {}).get("leftover_issues") or []) if isinstance(row, dict)}
        rest = [row for row in takeable_rows if identity(row) in cursor]
        return pick({"route": "listed", "issues": rest or takeable_rows})
    return _none(reason="none_ready")
