"""Remove exactly one prepared issue-label set."""

from lokay.gh_issues import remove_issue_labels
from lokay.proc._common import runner


def remove(prepared: dict) -> dict:
    try:
        remove_issue_labels(
            runner(),
            prepared["repo"],
            int(prepared["issue"]),
            list(prepared["remove_labels"]),
            live=bool(prepared.get("live")),
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": True,
            "route": "terminal",
            "reason": "remove_labels_failed",
            "error": str(exc),
        }
    return {"ok": True, "route": "removed"}
