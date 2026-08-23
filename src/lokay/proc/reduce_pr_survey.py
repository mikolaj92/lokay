"""Purely reduce authored repository-local PR-survey reactions."""


def reduce_state(*, prepared: dict, rows: list[dict], working: dict) -> dict:
    actions = list(working.get("actions") or [])
    prs = {}
    failed = []
    if prepared.get("recent_empty"):
        actions.append(
            {"step": "skip_pr_survey_recent_empty", "reason": "recent_empty"}
        )
    for row in rows:
        repo = str(row.get("repo") or "")
        if not repo:
            continue
        prs[repo] = list(row.get("prs") or [])
        actions.extend(row.get("actions") or [])
        if row.get("route") == "failed":
            failed.append(repo)
    errors = int(working.get("survey_errors") or 0) + sum(
        int(x.get("error_count") or 0) for x in rows
    )
    state = {
        **working,
        "actions": actions,
        "prs_by_repo": prs,
        "pr_survey_failed": sorted(failed),
        "remaining_prs": sum(len(v) for v in prs.values()),
        "actionable_prs": sum(int(x.get("actionable") or 0) for x in rows),
        "manual_prs": sum(int(x.get("manual") or 0) for x in rows),
        "survey_errors": errors,
    }
    return {"ok": True, "state": state, "skipped": bool(prepared.get("recent_empty"))}
