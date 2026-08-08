from __future__ import annotations

import json

from lokay.config import Config, RepoConfig
from lokay.models import Issue
from lokay.runner import Runner, gh_spec
from lokay.triage import is_parked, is_undecided

# Standard factory labels (create-if-missing so triage works on new repos).
_LABEL_META: dict[str, tuple[str, str]] = {
    "ai:ready": ("0E8A16", "Ready for AI agent work"),
    "ai:blocked": ("D73A4A", "AI agent work is blocked"),
    "ai:needs-feedback": ("B60205", "Needs human feedback before AI work"),
    "ai:generated": ("C5DEF5", "Generated or assisted by AI agent"),
    "ai:needs-review": ("D93F0B", "LLM PR review requests human judgment"),
    "ai:request-changes": ("FBCA04", "LLM PR review requested changes"),
    "ai:pr-opened": ("5319E7", "AI-generated PR opened"),
    "ai:in-progress": ("1D76DB", "AI agent work in progress"),
    "frozen": ("BFD4F2", "Intentionally paused for now"),
    "ai:frozen": ("BFD4F2", "Intentionally paused for now"),
}


def ensure_labels(runner: Runner, repo: str, labels: list[str], *, live: bool) -> None:
    """Create missing labels on repo (idempotent). Required before gh issue edit --add-label."""
    for label in labels:
        if not label:
            continue
        color, desc = _LABEL_META.get(label, ("ededed", "Lokay factory label"))
        # gh label create fails if exists unless --force; use create then ignore exists.
        result = runner.run(
            gh_spec(
                [
                    "label",
                    "create",
                    label,
                    "--repo",
                    repo,
                    "--color",
                    color,
                    "--description",
                    desc,
                ],
                timeout_seconds=60,
            ),
            live=live,
        )
        if not live:
            continue
        if result.returncode == 0:
            continue
        err_text = f"{result.stdout}\n{result.stderr}".lower()
        if "already exists" in err_text:
            continue
        # Retry with --force for older gh that uses different wording, else raise.
        forced = runner.run(
            gh_spec(
                [
                    "label",
                    "create",
                    label,
                    "--repo",
                    repo,
                    "--color",
                    color,
                    "--description",
                    desc,
                    "--force",
                ],
                timeout_seconds=60,
            ),
            live=live,
        )
        if forced.returncode != 0 and "already exists" not in f"{forced.stdout}\n{forced.stderr}".lower():
            raise RuntimeError(
                f"ensure label {label!r} on {repo} failed: {forced.stderr or forced.stdout}"
            )


def _eligible(assignees: list[str], config: Config) -> bool:
    if not config.assignee:
        return True
    if config.assignee in assignees:
        return True
    return (not assignees) and config.allow_unassigned


def _issue_from_row(repo_name: str, row: dict) -> Issue:
    labels = [lbl.get("name", "") for lbl in row.get("labels") or []]
    assignees = [a.get("login", "") for a in row.get("assignees") or []]
    return Issue(
        repo=repo_name,
        number=int(row["number"]),
        title=str(row.get("title") or ""),
        body=str(row.get("body") or ""),
        labels=labels,
        assignees=assignees,
        url=str(row.get("url") or ""),
    )


def list_ready_issues(runner: Runner, config: Config, repo: RepoConfig, *, live: bool) -> list[Issue]:
    args = [
        "issue",
        "list",
        "--repo",
        repo.name,
        "--state",
        "open",
        "--label",
        config.ready_label,
        "--json",
        "number,title,body,labels,assignees,url",
        "--limit",
        "50",
    ]
    result = runner.run_checked(gh_spec(args, timeout_seconds=60), live=live)
    if not live:
        return []
    issues: list[Issue] = []
    for row in json.loads(result.stdout or "[]"):
        issue = _issue_from_row(repo.name, row)
        if config.blocked_label in issue.labels:
            continue
        if is_parked(issue.labels):
            continue
        if not _eligible(issue.assignees, config):
            continue
        issues.append(issue)
    return issues


def list_inbox_issues(runner: Runner, config: Config, repo: RepoConfig, *, live: bool) -> list[Issue]:
    """Open issues not yet decided (no ready/blocked/needs-feedback labels)."""
    args = [
        "issue",
        "list",
        "--repo",
        repo.name,
        "--state",
        "open",
        "--json",
        "number,title,body,labels,assignees,url",
        "--limit",
        "50",
    ]
    result = runner.run_checked(gh_spec(args, timeout_seconds=60), live=live)
    if not live:
        return []
    out: list[Issue] = []
    for row in json.loads(result.stdout or "[]"):
        issue = _issue_from_row(repo.name, row)
        if not is_undecided(
            issue.labels,
            ready_label=config.ready_label,
            blocked_label=config.blocked_label,
            needs_feedback_label=config.needs_feedback_label,
        ):
            continue
        out.append(issue)
    return out


def add_issue_labels(
    runner: Runner, repo: str, number: int, labels: list[str], *, live: bool
) -> None:
    ensure_labels(runner, repo, labels, live=live)
    for label in labels:
        if not label:
            continue
        runner.run_checked(
            gh_spec(
                [
                    "issue",
                    "edit",
                    str(number),
                    "--repo",
                    repo,
                    "--add-label",
                    label,
                ]
            ),
            live=live,
        )


def remove_issue_labels(
    runner: Runner, repo: str, number: int, labels: list[str], *, live: bool
) -> None:
    for label in labels:
        if not label:
            continue
        runner.run_checked(
            gh_spec(
                [
                    "issue",
                    "edit",
                    str(number),
                    "--repo",
                    repo,
                    "--remove-label",
                    label,
                ]
            ),
            live=live,
        )


def comment_issue(runner: Runner, repo: str, number: int, body: str, *, live: bool) -> None:
    runner.run_checked(
        gh_spec(
            [
                "issue",
                "comment",
                str(number),
                "--repo",
                repo,
                "--body",
                body,
            ]
        ),
        live=live,
    )


def get_issue(runner: Runner, config: Config, repo: str, number: int, *, live: bool) -> Issue | None:
    result = runner.run(
        gh_spec(
            [
                "issue",
                "view",
                str(number),
                "--repo",
                repo,
                "--json",
                "number,title,body,labels,assignees,url,state",
            ]
        ),
        live=live,
    )
    if not live:
        return Issue(
            repo=repo,
            number=number,
            title=f"(dry-run) issue #{number}",
            body="",
            labels=[config.ready_label],
            assignees=[config.assignee],
            url=f"https://github.com/{repo}/issues/{number}",
        )
    if result.returncode != 0:
        return None
    row = json.loads(result.stdout or "{}")
    return Issue(
        repo=repo,
        number=int(row["number"]),
        title=str(row.get("title") or ""),
        body=str(row.get("body") or ""),
        labels=[lbl.get("name", "") for lbl in row.get("labels") or []],
        assignees=[a.get("login", "") for a in row.get("assignees") or []],
        url=str(row.get("url") or ""),
    )


def assign_issue(runner: Runner, config: Config, repo: str, number: int, *, live: bool) -> None:
    if not config.assignee:
        return
    runner.run_checked(
        gh_spec(
            [
                "issue",
                "edit",
                str(number),
                "--repo",
                repo,
                "--add-assignee",
                config.assignee,
            ]
        ),
        live=live,
    )


def close_issue(runner: Runner, repo: str, number: int, *, live: bool) -> None:
    runner.run_checked(
        gh_spec(["issue", "close", str(number), "--repo", repo]),
        live=live,
    )
