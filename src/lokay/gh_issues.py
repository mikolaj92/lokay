from __future__ import annotations

import json

from lokay.config import Config, RepoConfig
from lokay.models import Issue
from lokay.runner import Runner, gh_spec
from lokay.triage import is_undecided


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
