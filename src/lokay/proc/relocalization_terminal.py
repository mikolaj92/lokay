"""Select one closed off-goal relocalization result."""


def terminal(
    evidence: dict, changed: dict, offgoal: dict, approval: dict, written: dict
) -> dict:
    if written.get("route") == "success":
        return {
            "ok": True,
            "result": {k: v for k, v in written.items() if k not in {"route", "atom"}},
        }
    if evidence.get("route") == "terminal":
        reason = evidence.get("reason")
    elif changed.get("route") == "terminal":
        reason = changed.get("reason")
    elif offgoal.get("route") == "terminal":
        reason = offgoal.get("reason") or "on_goal"
    else:
        reason = approval.get("reason") or "off_goal_not_approved"
    return {
        "ok": True,
        "result": {
            "ok": True,
            "skipped": True,
            "reason": reason,
            "off_goal_paths": offgoal.get("off_goal_paths") or [],
            "restored_paths": offgoal.get("restored_paths") or [],
            "worktree": evidence.get("worktree"),
        },
    }
