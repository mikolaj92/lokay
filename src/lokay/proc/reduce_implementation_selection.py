"""Purely reduce authored repository-slot reactions into one selection."""


def reduce_state(*, prepared: dict, results: list[dict], working: dict) -> dict:
    actions = list(working.get("actions") or [])
    ready = dict(working.get("ready_by_repo") or {})
    clean = []
    remaining = int(working.get("remaining_ready") or 0)
    if prepared.get("route") == "no_budget":
        return {
            "ok": True,
            "route": "no_budget",
            "clean_repos": [],
            "issue_budget": prepared.get("issue_budget"),
            "actions": actions,
            "ready_by_repo": ready,
            "remaining_ready": remaining,
        }
    for row in results:
        repo, route, reason = (
            str(row.get("repo") or ""),
            str(row.get("route") or ""),
            str(row.get("reason") or ""),
        )
        if not repo:
            continue
        blocked = list(row.get("blocked") or [])
        if blocked:
            blocked_numbers = {int(item.get("number", -1)) for item in blocked}
            ready[repo] = [
                item
                for item in list(ready.get(repo) or [])
                if int(item.get("number", -1)) not in blocked_numbers
            ]
            remaining = max(0, remaining - len(blocked))
            actions.append(
                {
                    "step": "skip_stuck",
                    "repo": repo,
                    "exclude": sorted(blocked_numbers),
                    "reason": "issue is blocked in the stuck ledger; refuse issue_to_pr",
                }
            )
        if route == "eligible" and not clean:
            clean.append(repo)
        if route == "ineligible":
            step = {
                "actionable_pr": "skip_ready_open_ai_pr",
                "occupied": "skip_ready_repo_occupied",
                "pr_survey_failed": "skip_issue_to_pr_survey_failed",
                "executor_disabled": "skip_ready_agent_disabled",
                "outside_scope": "skip_issue_to_pr_outside_mini_scope",
            }.get(reason, "skip_implementation_repo")
            actions.append({"step": step, "repo": repo, "reason": reason})
    return {
        "ok": True,
        "route": "selected" if clean else "none",
        "clean_repos": clean,
        "issue_budget": prepared.get("issue_budget"),
        "actions": actions,
        "ready_by_repo": ready,
        "remaining_ready": remaining,
    }
