"""Add exactly one prepared issue-label set, or preserve an earlier terminal."""

from lokay.gh_issues import add_issue_labels
from lokay.proc._common import runner


def add(prepared: dict, removed: dict) -> dict:
    if removed.get("route") == "terminal":
        return {
            "ok": True,
            "route": "terminal",
            "reason": removed.get("reason") or "issue_closed",
        }
    labels = list(prepared.get("add_labels") or [])
    try:
        if labels:
            add_issue_labels(
                runner(),
                prepared["repo"],
                int(prepared["issue"]),
                labels,
                live=bool(prepared.get("live")),
            )
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": True,
            "route": "terminal",
            "reason": "add_labels_failed",
            "error": str(exc),
        }
    return {"ok": True, "route": "comment" if prepared.get("comment") else "done"}
