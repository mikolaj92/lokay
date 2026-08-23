"""Purely reduce one conflict-resolution reaction into working state."""


def reduce_state(
    *,
    working: dict,
    target: dict,
    closed: dict,
    resolved: dict,
    cleared: dict,
    ready: dict,
) -> dict:
    actions = list(working.get("actions") or [])
    repo, pr = str(target.get("repo") or ""), int(target.get("pr") or 0)
    success = closed.get("route") == "closed"
    actions.extend(
        [
            {
                "step": "pr_conflict",
                "repo": repo,
                "pr": pr,
                "mergeable": target.get("mergeable"),
                "branch": target.get("head_ref"),
            },
            {
                "step": "pr_close_conflict",
                "repo": repo,
                "pr": pr,
                **dict(closed.get("close") or {}),
            },
        ]
    )
    if not success:
        return {
            **working,
            "actions": actions,
            "conflict_route": closed.get("route") or "failed",
            "conflict_closed": 0,
        }
    prs = dict(working.get("prs_by_repo") or {})
    prs[repo] = [
        row for row in list(prs.get(repo) or []) if int(row.get("number") or 0) != pr
    ]
    state = {
        **working,
        "actions": actions,
        "prs_by_repo": prs,
        "progress": int(working.get("progress") or 0) + 1,
        "conflict_route": "closed",
        "conflict_closed": 1,
    }
    if resolved.get("route") != "issue":
        return state
    issue = int(resolved["issue"])
    actions.append(
        {
            "step": "re_ready_after_conflict",
            "repo": repo,
            "issue": issue,
            "pr": pr,
            **dict(ready.get("ready") or {}),
        }
    )
    state["stuck"] = dict(cleared.get("stuck") or working.get("stuck") or {})
    if ready.get("applied"):
        rows = dict(working.get("ready_by_repo") or {})
        rows.setdefault(repo, []).append(
            {
                "number": issue,
                "repo": repo,
                "title": str(target.get("title") or f"issue {issue}"),
            }
        )
        state["ready_by_repo"] = rows
        state["remaining_ready"] = int(working.get("remaining_ready") or 0) + 1
    return state
