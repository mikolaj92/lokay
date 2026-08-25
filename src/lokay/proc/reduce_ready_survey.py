"""Purely reduce visible ready-repo reactions into one survey state."""

from lokay.proc.catalog_work import remaining_ready_count, work_by_repo


def reduce_state(*, prepared: dict, results: list[dict], working: dict) -> dict:
    ready = dict(working.get("ready_by_repo") or {})
    failed = list(working.get("ready_survey_failed") or [])
    actions = list(working.get("actions") or [])
    progress = int(working.get("progress") or 0)
    errors = int(working.get("survey_errors") or 0)
    for repo in prepared.get("skipped_repos") or []:
        ready[str(repo)] = []
    if prepared.get("recent_empty"):
        actions.append(
            {"step": "skip_ready_survey_recent_empty", "reason": "recent_empty"}
        )
    for row in results:
        repo, route = str(row.get("repo") or ""), str(row.get("route") or "")
        if not repo:
            continue
        ready[repo] = list(row.get("implementable") or [])
        if route == "cold":
            actions.append({"step": "skip_cold_repo", "repo": repo, "survey": "ready"})
        if route == "failed":
            errors += 1
            failed.append(repo)
        if row.get("covered"):
            actions.append(
                {
                    "step": "skip_ready_with_open_pr",
                    "repo": repo,
                    "issues": sorted(int(x["number"]) for x in row["covered"]),
                }
            )
        if row.get("blocked"):
            actions.append(
                {
                    "step": "skip_stuck",
                    "repo": repo,
                    "exclude": sorted(int(x["number"]) for x in row["blocked"]),
                }
            )
        parked = dict(row.get("parked") or {})
        if parked:
            actions.append({"step": "park_stuck", "repo": repo, **parked})
            progress += int(bool(parked.get("applied")))
    # Inbox is work. A leftover ready-only catalog would ignore unlabeled issues.
    ready = work_by_repo({**working, "ready_by_repo": ready})
    remaining = remaining_ready_count(ready)
    return {
        "ok": True,
        "actions": actions,
        "progress": progress,
        "ready_by_repo": ready,
        "ready_survey_failed": sorted(set(failed)),
        "remaining_ready": remaining,
        "remaining_ready_with_pr": sum(
            len(row.get("covered") or []) for row in results
        ),
        "survey_errors": errors,
        "skipped": bool(prepared.get("recent_empty")),
    }
