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


def launch(candidate: dict, *, config_path: str | None) -> dict:
    result = detach_issue_to_pr(
        repo=str(candidate["repo"]),
        issue=int(candidate["issue"]),
        config_path=config_path,
    )
    leftover, leftover_issues = leftover_without_repo(
        candidate, str(candidate.get("repo") or "")
    )
    return {
        **dict(candidate),
        "ok": True,
        "route": "started" if result.get("ok") else "failed",
        "launch": result,
        "leftover": leftover,
        "leftover_issues": leftover_issues,
    }
