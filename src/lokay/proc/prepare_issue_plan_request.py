"""Normalize one issue-plan request into a closed Issue fact."""

from lokay.models import Issue


def prepare(
    *,
    worktree: str,
    issue_raw: dict,
    repo: str,
    issue: int | None,
    title: str,
    body: str,
    url: str,
    rel_path: str,
) -> dict:
    value = (
        Issue.from_dict(issue_raw)
        if issue_raw
        else Issue(
            repo=repo,
            number=int(issue or 0),
            title=title,
            body=body,
            labels=[],
            assignees=[],
            url=url,
        )
    )
    return {
        "ok": True,
        "worktree": worktree,
        "issue": value.to_dict(),
        "rel_path": rel_path,
    }
