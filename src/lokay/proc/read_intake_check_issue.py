"""Read one issue for one mechanical intake check."""

from lokay.gh_issues import get_issue
from lokay.proc._common import runner


def read(request: dict, *, config: object) -> dict:
    if request.get("route") != "read":
        return {
            "ok": True,
            "route": "unused",
            "reason": request.get("reason"),
            "issue": None,
        }
    try:
        issue = get_issue(
            runner(),
            config,
            request["repo"],
            int(request["issue"]),
            live=bool(request.get("live")),
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": True,
            "route": "terminal",
            "reason": "issue_probe_failed",
            "error": str(exc),
        }
    return {
        "ok": True,
        "route": "resolve" if issue else "terminal",
        "reason": "" if issue else "issue_missing",
        "issue": issue.to_dict() if issue else None,
    }
