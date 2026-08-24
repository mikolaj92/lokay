"""Select one closed pull-request publication result."""


def terminal(
    request: dict, existing: dict, issue: dict, classified: dict, created: dict
) -> dict:
    common = {
        "repo": request.get("repo"),
        "head": request.get("head"),
        "issue": request.get("issue"),
    }
    if existing.get("route") == "existing":
        pull = existing.get("pull") or {}
        return {
            "ok": True,
            "result": {
                "ok": True,
                "planned": False,
                "existing": True,
                "pr": pull.get("number"),
                "pull": pull,
                **common,
            },
        }
    if created.get("route") == "created":
        pull = created.get("pull") or {}
        return {
            "ok": True,
            "result": {
                "ok": True,
                "planned": created.get("planned"),
                "existing": False,
                "pr": pull.get("number"),
                "pull": pull,
                **common,
            },
        }
    reason = (
        classified.get("reason")
        or created.get("reason")
        or existing.get("reason")
        or issue.get("reason")
        or "pr_create_failed"
    )
    return {
        "ok": True,
        "result": {
            "ok": False,
            "reason": reason,
            "error": created.get("error")
            or existing.get("error")
            or issue.get("error")
            or reason.replace("_", " "),
            "issue_state": classified.get("issue_state") or issue.get("issue_state"),
            **common,
        },
    }
