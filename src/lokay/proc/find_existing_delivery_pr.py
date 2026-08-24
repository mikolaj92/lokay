"""Read one covering delivery PR for a normalized issue identity."""

from lokay.gh_prs import find_pr_fixing_issue
from lokay.proc._common import runner


def find(request: dict, *, live: bool) -> dict:
    if request.get("issue") is None:
        return {"ok": True, "route": "none", "pull": None}
    try:
        pull = find_pr_fixing_issue(
            runner(), request["repo"], int(request["issue"]), live=live
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": True,
            "route": "terminal",
            "reason": "covering_pr_probe_failed",
            "error": str(exc),
            "pull": None,
        }
    return {"ok": True, "route": "existing" if pull else "none", "pull": pull}
