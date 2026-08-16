from __future__ import annotations

import json

from lokay.config import Config, RepoConfig
from lokay.gh_rate import survey_pace
from lokay.models import Issue
from lokay.runner import Runner, gh_spec
from lokay.triage import is_parked, is_undecided

# Standard factory labels (create-if-missing so triage works on new repos).
_LABEL_META: dict[str, tuple[str, str]] = {
    "ai:ready": ("0E8A16", "Ready for AI agent work"),
    "ai:blocked": ("D73A4A", "AI agent work is blocked"),
    "ai:needs-feedback": ("B60205", "Rare residual — needs human feedback"),
    "ai:tracker": ("5319E7", "Parent tracker after auto-split (not implementable)"),
    "ai:generated": ("C5DEF5", "Generated or assisted by AI agent"),
    "ai:needs-review": ("D93F0B", "LLM PR review requests human judgment"),
    "ai:request-changes": ("FBCA04", "LLM PR review requested changes"),
    "ai:pr-opened": ("5319E7", "AI-generated PR opened"),
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


def _author_login(row: dict) -> str:
    author = row.get("author")
    if isinstance(author, dict):
        return str(author.get("login") or "")
    return str(author or "")


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
        state=str(row.get("state") or "OPEN").upper(),
        author=_author_login(row),
    )


def list_labeled_issues(
    runner: Runner, config: Config, repo: RepoConfig, *, label: str, live: bool
) -> list[Issue]:
    """Open issues carrying one ledger/factory label (no ready-only filter)."""
    if live:
        survey_pace(config)
    args = [
        "issue",
        "list",
        "--repo",
        repo.name,
        "--state",
        "open",
        "--label",
        label,
        "--json",
        "number,title,body,labels,assignees,author,url",
        "--limit",
        "50",
    ]
    result = runner.run_checked(gh_spec(args, timeout_seconds=60), live=live)
    if not live:
        return []
    return [_issue_from_row(repo.name, row) for row in json.loads(result.stdout or "[]")]


def list_ready_issues(runner: Runner, config: Config, repo: RepoConfig, *, live: bool) -> list[Issue]:
    if live:
        survey_pace(config)
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
        "number,title,body,labels,assignees,author,url",
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
    if live:
        survey_pace(config)
    args = [
        "issue",
        "list",
        "--repo",
        repo.name,
        "--state",
        "open",
        "--json",
        "number,title,body,labels,assignees,author,url",
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


def _remove_label_already_absent(label: str, stdout: str, stderr: str) -> bool:
    blob = f"{stderr}\n{stdout}"
    return f"'{label}' not found" in blob or f'"{label}" not found' in blob


def remove_issue_labels(
    runner: Runner, repo: str, number: int, labels: list[str], *, live: bool
) -> None:
    for label in labels:
        if not label:
            continue
        spec = gh_spec(
            [
                "issue",
                "edit",
                str(number),
                "--repo",
                repo,
                "--remove-label",
                label,
            ]
        )
        result = runner.run(spec, live=live)
        if not live or result.returncode == 0:
            continue
        if _remove_label_already_absent(label, result.stdout, result.stderr):
            continue
        raise RuntimeError(
            f"command failed ({result.returncode}): {spec.display()}\n"
            f"stdout: {result.stdout[-2000:]}\nstderr: {result.stderr[-2000:]}"
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
                "number,title,body,labels,assignees,author,url,state",
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
            state="OPEN",
            author=config.assignee,
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
        state=str(row.get("state") or "OPEN").upper(),
        author=_author_login(row),
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


def create_issue(
    runner: Runner,
    *,
    repo: str,
    title: str,
    body: str,
    labels: list[str] | None = None,
    live: bool,
) -> dict:
    """Create one GitHub issue. Returns {number, url} (or planned stub when dry)."""
    label_list = [x for x in (labels or []) if x]
    if label_list:
        ensure_labels(runner, repo, label_list, live=live)
    args = [
        "issue",
        "create",
        "--repo",
        repo,
        "--title",
        title,
        "--body",
        body,
    ]
    for label in label_list:
        args.extend(["--label", label])
    result = runner.run_checked(gh_spec(args, timeout_seconds=120), live=live)
    if not live:
        return {"planned": True, "title": title, "repo": repo}
    # gh prints URL on stdout
    url = (result.stdout or "").strip().splitlines()[-1] if (result.stdout or "").strip() else ""
    number = 0
    if "/issues/" in url:
        try:
            number = int(url.rstrip("/").rsplit("/", 1)[-1])
        except ValueError:
            number = 0
    if number <= 0:
        # Fallback: view by URL search is fragile; re-list latest open matching title.
        listed = runner.run(
            gh_spec(
                [
                    "issue",
                    "list",
                    "--repo",
                    repo,
                    "--state",
                    "open",
                    "--json",
                    "number,title,url",
                    "--limit",
                    "5",
                ],
                timeout_seconds=60,
            ),
            live=True,
        )
        if listed.returncode == 0:
            for row in json.loads(listed.stdout or "[]"):
                if str(row.get("title") or "") == title:
                    return {
                        "number": int(row["number"]),
                        "url": str(row.get("url") or ""),
                        "title": title,
                        "repo": repo,
                    }
        raise RuntimeError(f"create issue on {repo} succeeded but number unknown: {url!r}")
    return {"number": number, "url": url, "title": title, "repo": repo}


def list_issues_with_label(
    runner: Runner,
    config: Config,
    repo: RepoConfig,
    *,
    label: str,
    live: bool,
    limit: int = 50,
) -> list[Issue]:
    """Open issues carrying a label (read-only survey helper)."""
    if not label:
        return []
    if live:
        survey_pace(config)
    args = [
        "issue",
        "list",
        "--repo",
        repo.name,
        "--state",
        "open",
        "--label",
        label,
        "--json",
        "number,title,body,labels,assignees,author,url",
        "--limit",
        str(max(1, min(int(limit), 100))),
    ]
    result = runner.run_checked(gh_spec(args, timeout_seconds=60), live=live)
    if not live:
        return []
    return [_issue_from_row(repo.name, row) for row in json.loads(result.stdout or "[]")]
