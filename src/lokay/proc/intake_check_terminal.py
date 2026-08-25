"""Select one closed mechanical intake-check result."""

from lokay.intake import referenced_pr_numbers
from lokay.models import Issue


def terminal(request: dict, issue: dict, clone: dict, selected: dict) -> dict:
    if request.get("route") == "terminal":
        return {
            "ok": True,
            "result": {
                "ok": True,
                "skipped": True,
                "reason": request.get("reason"),
                "repo": request.get("repo"),
                "issue": request.get("issue"),
                "check": request.get("check"),
            },
        }
    if selected.get("route") == "selected":
        raw = issue.get("issue") or {}
        return {
            "ok": True,
            "result": {
                "ok": True,
                "offline": not request.get("live"),
                "repo": request.get("repo"),
                "issue": raw,
                "check": selected.get("check"),
                "referenced_prs": referenced_pr_numbers(Issue.from_dict(raw)),
                "clone_path": clone.get("clone_path"),
            },
        }
    reason = selected.get("reason") or issue.get("reason") or "intake_check_failed"
    return {
        "ok": True,
        "result": {
            "ok": False,
            "reason": reason,
            "error": selected.get("error")
            or issue.get("error")
            or reason.replace("_", " "),
            "repo": request.get("repo"),
            "issue": request.get("issue"),
        },
    }
