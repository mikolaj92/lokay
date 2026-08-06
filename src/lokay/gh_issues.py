from __future__ import annotations

import json

from lokay.config import Config, RepoConfig
from lokay.models import Issue
from lokay.runner import Runner, gh_spec


def _eligible(assignees: list[str], config: Config) -> bool:
    if not config.assignee:
        return True
    if config.assignee in assignees:
        return True
    return (not assignees) and config.allow_unassigned


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
        labels = [lbl.get("name", "") for lbl in row.get("labels") or []]
        if config.blocked_label in labels:
            continue
        assignees = [a.get("login", "") for a in row.get("assignees") or []]
        if not _eligible(assignees, config):
            continue
        issues.append(
            Issue(
                repo=repo.name,
                number=int(row["number"]),
                title=str(row.get("title") or ""),
                body=str(row.get("body") or ""),
                labels=labels,
                assignees=assignees,
                url=str(row.get("url") or ""),
            )
        )
    return issues


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
