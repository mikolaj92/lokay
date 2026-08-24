"""Select one closed deterministic issue-plan result."""


def terminal(request: dict, approach: dict, authorized: dict, write: dict) -> dict:
    issue = request.get("issue") or {}
    common = {
        "repo": issue.get("repo"),
        "issue": issue.get("number"),
        "worktree": request.get("worktree"),
        "approach_path": approach.get("approach_path"),
        "approach_rel": request.get("rel_path"),
        "source": approach.get("source"),
        "plan": approach.get("plan"),
        "content": approach.get("content"),
    }
    if write.get("route") in {"written", "planned"}:
        return {
            "ok": True,
            "result": {
                "ok": True,
                "planned": write.get("route") == "planned",
                "wrote": write.get("route") == "written",
                **common,
            },
        }
    reason = write.get("reason") or authorized.get("reason") or "approach_write_failed"
    return {
        "ok": True,
        "result": {
            "ok": False,
            "reason": reason,
            "error": write.get("error") or reason.replace("_", " "),
            "wrote": False,
            **common,
        },
    }
