"""Normalize parent delivery facts for the local-repair child Fala."""


def prepare(
    *,
    worktree: str,
    repo: str,
    issue: int | None,
    issue_raw: dict,
    branch: str,
    first_test: dict,
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
        "branch": branch,
        "first_test": dict(first_test or {}),
        "live": bool(live),
    }
