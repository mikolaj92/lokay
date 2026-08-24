"""Purely authorize publication from a fresh issue-state fact."""


def classify(existing: dict, issue: dict) -> dict:
    if existing.get("route") in {"existing", "terminal"}:
        return {
            "ok": True,
            "route": "terminal",
            "reason": (
                "existing_pr"
                if existing.get("route") == "existing"
                else existing.get("reason")
            ),
        }
    if issue.get("route") == "open":
        return {"ok": True, "route": "create", "reason": ""}
    state = issue.get("issue_state")
    return {
        "ok": True,
        "route": "create" if state == "OPEN" else "terminal",
        "reason": "" if state == "OPEN" else (issue.get("reason") or "issue_closed"),
        "issue_state": state,
    }
