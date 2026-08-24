"""Select one closed physical real-diff result."""


def terminal(
    worktree: dict,
    changed: dict,
    kind: dict,
    localize: dict,
    presence: dict,
    ticket: dict,
    scope: dict,
    progress: dict,
) -> dict:
    reason = ""
    for fact in (worktree, changed, localize, presence, ticket, scope, progress):
        if fact.get("route") == "terminal":
            reason = str(fact.get("reason") or "real_diff_failed")
            break
    real = progress.get("route") == "real" and not reason
    result = {
        "ok": real,
        "real": real,
        "reason": reason,
        "kind": kind.get("kind"),
        "paths": changed.get("paths") or [],
        "worktree": worktree.get("worktree"),
        "base": changed.get("base"),
    }
    for fact, key in (
        (presence, "required_paths"),
        (ticket, "extra_paths"),
        (scope, "off_goal_paths"),
        (scope, "localized_paths"),
    ):
        if fact.get(key):
            result[key] = fact[key]
    if not real:
        result["error"] = "refusing: " + reason.replace("_", " ")
    return {"ok": True, "result": result}
