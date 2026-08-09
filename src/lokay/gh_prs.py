from __future__ import annotations

import json
from typing import Any

from lokay.config import Config, RepoConfig
from lokay.gh_issues import ensure_labels
from lokay.models import PullRequest
from lokay.runner import CommandResult, Runner, gh_spec


def _label_names(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    if not all(
        isinstance(label, dict) and isinstance(label.get("name"), str)
        for label in value
    ):
        return None
    return [str(label["name"]) for label in value]


def list_open_ai_prs(runner: Runner, config: Config, repo: RepoConfig, *, live: bool) -> list[PullRequest]:
    args = [
        "pr",
        "list",
        "--repo",
        repo.name,
        "--state",
        "open",
        "--json",
        "number,title,body,headRefName,headRefOid,author,url,isDraft,mergeable,labels",
        "--limit",
        "50",
    ]
    result = runner.run_checked(gh_spec(args, timeout_seconds=60), live=live)
    if not live:
        return []
    prefix = config.branch_prefix.rstrip("/") + "/"
    out: list[PullRequest] = []
    for row in json.loads(result.stdout or "[]"):
        head = str(row.get("headRefName") or "")
        if not head.startswith(prefix):
            continue
        author = ""
        if isinstance(row.get("author"), dict):
            author = str(row["author"].get("login") or "")
        out.append(
            PullRequest(
                repo=repo.name,
                number=int(row["number"]),
                title=str(row.get("title") or ""),
                body=str(row.get("body") or ""),
                head_ref=head,
                head_sha=str(row.get("headRefOid") or ""),
                author=author,
                url=str(row.get("url") or ""),
                is_draft=bool(row.get("isDraft")),
                mergeable=str(row["mergeable"]) if row.get("mergeable") is not None else None,
                labels=_label_names(row.get("labels")),
            )
        )
    return out


def create_pr(
    runner: Runner,
    *,
    repo: str,
    title: str,
    body: str,
    head: str,
    base: str = "main",
    live: bool,
) -> dict[str, Any]:
    result = runner.run_checked(
        gh_spec(
            [
                "pr",
                "create",
                "--repo",
                repo,
                "--title",
                title,
                "--body",
                body,
                "--head",
                head,
                "--base",
                base,
            ],
            timeout_seconds=120,
        ),
        live=live,
    )
    if not live:
        return {"planned": True, "head": head, "title": title}
    url = (result.stdout or "").strip().splitlines()[-1] if result.stdout else ""
    return {"url": url, "head": head, "title": title}


def add_pr_labels(runner: Runner, repo: str, number: int, labels: list[str], *, live: bool) -> None:
    ensure_labels(runner, repo, labels, live=live)
    for label in labels:
        runner.run(
            gh_spec(["pr", "edit", str(number), "--repo", repo, "--add-label", label]),
            live=live,
        )


def pr_checks_report(
    runner: Runner, repo: str, number: int, *, live: bool
) -> dict[str, Any]:
    """Classify PR checks for triage.

    status:
      - passed: all required checks green (gh exit 0)
      - failed: at least one check failed
      - pending: checks still running (gh often exit 8)
      - none: repository reports no checks on the head branch
      - offline: dry-run / no network
    """
    result = runner.run(
        gh_spec(["pr", "checks", str(number), "--repo", repo], timeout_seconds=120),
        live=live,
    )
    if not live:
        return {
            "status": "offline",
            "green": False,
            "no_checks": False,
            "text": "dry-run",
        }
    text = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
    low = text.lower()
    if "no checks reported" in low:
        return {
            "status": "none",
            "green": False,
            "no_checks": True,
            "text": text or "no checks reported",
        }
    if result.returncode == 0:
        return {
            "status": "passed",
            "green": True,
            "no_checks": False,
            "text": text or "checks passed",
        }
    # gh: pending checks commonly exit 8
    if result.returncode == 8 or "pending" in low or "in_progress" in low:
        return {
            "status": "pending",
            "green": False,
            "no_checks": False,
            "text": text or f"checks pending (exit {result.returncode})",
        }
    return {
        "status": "failed",
        "green": False,
        "no_checks": False,
        "text": text or f"checks exit {result.returncode}",
    }


def merge_pr(runner: Runner, repo: str, number: int, *, live: bool) -> CommandResult:
    return runner.run_checked(
        gh_spec(
            [
                "pr",
                "merge",
                str(number),
                "--repo",
                repo,
                "--merge",
                "--delete-branch=false",
            ],
            timeout_seconds=180,
        ),
        live=live,
    )


def close_pr(
    runner: Runner,
    repo: str,
    number: int,
    *,
    live: bool,
    comment: str = "",
) -> CommandResult:
    """Close an open PR (no delete-branch). Optional comment explains why."""
    args = ["pr", "close", str(number), "--repo", repo]
    if comment:
        args.extend(["--comment", comment])
    return runner.run_checked(gh_spec(args, timeout_seconds=120), live=live)


def view_pr(runner: Runner, repo: str, number: int, *, live: bool) -> dict[str, Any]:
    result = runner.run_checked(
        gh_spec(
            [
                "pr",
                "view",
                str(number),
                "--repo",
                repo,
                "--json",
                "number,title,body,comments,commits,statusCheckRollup,headRefName,url",
            ],
            timeout_seconds=60,
        ),
        live=live,
    )
    if not live:
        return {}
    return json.loads(result.stdout or "{}")
