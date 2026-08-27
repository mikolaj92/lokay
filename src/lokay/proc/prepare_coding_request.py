"""Normalize parent delivery facts for the coding-execution child Fala."""


def prepare(
    *,
    worktree: str,
    repo: str,
    issue: int | None,
    issue_raw: dict,
    localize: dict,
    branch: str,
    live: bool,
) -> dict:
    raw = dict(issue_raw or {})
    if issue is not None:
        raw.setdefault("number", int(issue))
    if repo:
        raw.setdefault("repo", repo)
    return {
        "ok": True,
        "worktree": worktree,
        "repo": repo,
        "issue": issue,
        "issue_raw": raw,
        "localize": dict(localize or {}),
        "branch": branch,
        "live": bool(live),
    }
