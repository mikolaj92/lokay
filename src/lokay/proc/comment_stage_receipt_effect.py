"""Post exactly one prepared issue-stage receipt."""

from lokay.gh_issues import comment_issue
from lokay.proc._common import runner


def comment(prepared: dict) -> dict:
    try:
        comment_issue(
            runner(),
            prepared["repo"],
            int(prepared["issue"]),
            str(prepared["comment"]),
            live=bool(prepared.get("live")),
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": True,
            "route": "terminal",
            "reason": "stage_comment_failed",
            "error": str(exc),
        }
    return {"ok": True, "route": "done"}
