"""Launch one detached issue-to-PR worker after all Fala gates pass."""

from lokay.proc.detach_issue_to_pr import detach_issue_to_pr


def leftover_without_repo(candidate: dict, repo: str) -> tuple[int, list[dict]]:
    """A live or started receipt occupies the whole repo. Walk past it."""
    leftover_issues = [
        dict(row)
        for row in list(candidate.get("leftover_issues") or [])
        if isinstance(row, dict) and str(row.get("repo") or "") != str(repo)
    ]
    return len(leftover_issues), leftover_issues


def launch(
    candidate: dict,
    *,
    config_path: str | None,
    live: bool = True,
    budget: int | None = None,
    live_count: int | None = None,
) -> dict:
    if not live:
        return {
            **dict(candidate),
            "ok": True,
            "route": "skipped",
            "reason": "dry_run",
        }
    occupied = live_count
    if occupied is None and budget is not None:
        from lokay.proc.issue_delivery_occupancy import live_issue_to_pr_receipts

        occupied = len(live_issue_to_pr_receipts())
    if occupied is not None and int(occupied) > 0:
        return {
            **dict(candidate),
            "ok": True,
            "route": "busy",
            "reason": "global_occupancy",
            "spent": int(occupied),
            "budget": None if budget is None else max(0, int(budget)),
        }
    result = detach_issue_to_pr(
        repo=str(candidate["repo"]),
        issue=int(candidate["issue"]),
        config_path=config_path,
    )
    leftover, leftover_issues = leftover_without_repo(
        candidate, str(candidate.get("repo") or "")
    )
    if result.get("ok"):
        route = "started"
    elif result.get("reason") == "repo_lock_busy":
        route = "busy"
    else:
        route = "failed"
    return {
        **dict(candidate),
        "ok": True,
        "route": route,
        "launch": result,
        "leftover": leftover,
        "leftover_issues": leftover_issues,
    }
