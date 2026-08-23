"""Purely reduce authored repository-local inbox reactions into pass state."""


def reduce_state(*, prepared: dict, rows: list[dict], working: dict) -> dict:
    actions = list(working.get("actions") or [])
    by_repo = {}
    issues_by_repo = {}
    failed = []
    if prepared.get("recent_empty"):
        actions.append(
            {"step": "skip_inbox_survey_recent_empty", "reason": "recent_empty"}
        )
    for row in rows:
        repo = str(row.get("repo") or "")
        if not repo:
            continue
        issues = list(row.get("issues") or [])
        by_repo[repo] = len(issues)
        issues_by_repo[repo] = issues
        actions.extend(row.get("actions") or [])
        if row.get("route") == "failed":
            failed.append(repo)
    errors = int(working.get("survey_errors") or 0) + sum(
        int(x.get("error_count") or 0) for x in rows
    )
    state = {
        **working,
        "actions": actions,
        "inbox_by_repo": by_repo,
        "inbox_issues_by_repo": issues_by_repo,
        "inbox_survey_failed": sorted(failed),
        "remaining_inbox": sum(by_repo.values()),
        "survey_errors": errors,
    }
    return {"ok": True, "state": state, "skipped": bool(prepared.get("recent_empty"))}
