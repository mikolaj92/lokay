"""Materialize one repository-local PR-survey reaction."""


def record(prepared: dict, selected: dict, classified: dict) -> dict:
    row = dict(classified if classified.get("ok") else selected)
    repo = str(row.get("repo") or "")
    route = str(row.get("route") or "")
    actions = []
    if route == "outside_mini":
        actions.append(
            {
                "step": "skip_pr_survey_outside_mini_scope",
                "repo": repo,
                "reason": f"mini lokay only surveys PRs for {prepared['mini_repo']}",
            }
        )
    elif route == "cold":
        actions.append({"step": "skip_cold_repo", "repo": repo, "survey": "prs"})
    elif route in {"failed", "record"}:
        actions.append(
            {"step": "list_prs", "repo": repo, **dict(row.get("listed") or {})}
        )
    return {**row, "actions": actions, "error_count": int(route == "failed")}
