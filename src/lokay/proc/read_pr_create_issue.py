"""Re-read one issue immediately before PR publication."""

from lokay.gh_issues import get_issue
from lokay.proc._common import runner


def read(request: dict, *, config: object, live: bool) -> dict:
    if request.get("issue") is None:
        return {"ok": True, "route": "open", "issue_state": None}
    try:
        issue = get_issue(
            runner(), config, request["repo"], int(request["issue"]), live=live
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": True,
            "route": "terminal",
            "reason": "issue_probe_failed",
            "error": str(exc),
            "issue_state": "UNKNOWN",
        }
    state = "MISSING" if issue is None else str(issue.state or "").upper()
    return {"ok": True, "route": "classify", "issue_state": state}
