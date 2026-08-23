"""Materialize one repository-local inbox-survey reaction."""


def record(prepared: dict, selected: dict, classified: dict) -> dict:
    row = dict(classified if classified.get("ok") else selected)
    repo = str(row.get("repo") or "")
    route = str(row.get("route") or "")
    actions = []
    if route == "outside_mini":
        actions.append(
            {
                "step": "skip_inbox_survey_outside_mini_scope",
                "repo": repo,
                "reason": f"mini mill only surveys inbox for {prepared['mini_repo']}",
            }
        )
    elif route == "cold":
        actions.append({"step": "skip_cold_repo", "repo": repo, "survey": "inbox"})
    elif route in {"failed", "record"}:
        actions.append(
            {"step": "list_inbox", "repo": repo, **dict(row.get("listed") or {})}
        )
    if row.get("blocked"):
        actions.append(
            {"step": "skip_inbox_stuck_blocked", "repo": repo, "issues": row["blocked"]}
        )
    return {**row, "actions": actions, "error_count": int(route == "failed")}
