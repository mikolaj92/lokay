"""Purely prove that changed paths contain a required issue path."""


def classify(changed: dict, issue: dict) -> dict:
    if issue.get("route") != "required":
        return {"ok": True, "route": "continue", "reason": "", "required_paths": []}
    required = issue.get("paths") or []
    present = bool(required) and not {
        x.removeprefix("./") for x in changed.get("paths") or []
    }.isdisjoint(required)
    return {
        "ok": True,
        "route": "continue" if present else "terminal",
        "reason": "" if present else "ticket_scope_miss",
        "required_paths": required,
    }
