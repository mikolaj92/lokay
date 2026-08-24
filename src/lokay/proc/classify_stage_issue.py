"""Purely authorize one stage transition from a fresh issue fact."""


def classify(issue: dict, prepared: dict) -> dict:
    state = issue.get("issue_state")
    return {
        "ok": True,
        "route": (
            "remove"
            if state == "OPEN" and prepared.get("remove_labels")
            else ("add" if state == "OPEN" else "terminal")
        ),
        "reason": "" if state == "OPEN" else (issue.get("reason") or "issue_closed"),
        "issue_state": state,
    }
