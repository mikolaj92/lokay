from __future__ import annotations

import json
import re
from typing import Any

from lokay.config import Config, RepoConfig
from lokay.gh_issues import ensure_labels
from lokay.gh_rate import (
    is_transient_github_text,
    parse_survey_list,
    survey_list_cap,
    survey_pace,
)
from lokay.models import PullRequest
from lokay.runner import CommandResult, Runner, gh_spec


def gh_json(
    runner: Runner, args: list[str], *, live: bool, timeout_seconds: int = 120
) -> dict[str, Any]:
    result = runner.run_checked(gh_spec(args, timeout_seconds=timeout_seconds), live=live)
    if not live:
        return {}
    return json.loads(result.stdout or "{}")


def gh_text(
    runner: Runner,
    args: list[str],
    *,
    live: bool,
    timeout_seconds: int = 120,
    require_success: bool = False,
) -> str:
    result = runner.run(gh_spec(args, timeout_seconds=timeout_seconds), live=live)
    if not live:
        return ""
    text = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
    if require_success and result.returncode != 0:
        raise RuntimeError(text or f"gh text command failed with exit {result.returncode}")
    return text


def comment_bodies(view: dict[str, Any]) -> list[str]:
    comments = view.get("comments") or []
    if not isinstance(comments, list):
        return []
    bodies: list[str] = []
    for row in comments:
        if isinstance(row, dict) and isinstance(row.get("body"), str):
            bodies.append(row["body"])
        elif isinstance(row, str):
            bodies.append(row)
    return bodies


def comment_pr(runner: Runner, repo: str, number: int, body: str, *, live: bool) -> None:
    runner.run_checked(
        gh_spec(
            ["pr", "comment", str(number), "--repo", repo, "--body", body],
            timeout_seconds=60,
        ),
        live=live,
    )


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
    if live:
        survey_pace(config)
    cap = survey_list_cap()
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
        str(cap),
    ]
    result = runner.run_checked(gh_spec(args, timeout_seconds=60), live=live)
    if not live:
        return []
    prefix = config.branch_prefix.rstrip("/") + "/"
    out: list[PullRequest] = []
    for row in parse_survey_list(
        result.stdout, kind="open-ai-pr", repo=repo.name, cap=cap
    ):
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


def find_pr_fixing_issue(
    runner: Runner,
    repo: str,
    issue: int,
    *,
    live: bool,
    merged_only: bool = False,
) -> dict[str, Any] | None:
    """Return a closing PR, optionally requiring it to be merged."""
    result = runner.run_checked(
        gh_spec(
            [
                "api",
                "--method",
                "GET",
                f"repos/{repo}/pulls",
                "-f",
                "state=all",
                "-f",
                "per_page=100",
                "--paginate",
                "--slurp",
            ],
            timeout_seconds=120,
        ),
        live=live,
    )
    if not live:
        return None
    pages = json.loads(result.stdout or "[]")
    if not isinstance(pages, list):
        raise ValueError("closing PR survey must be a JSON list")
    if all(isinstance(row, dict) for row in pages):
        rows = pages
    elif all(isinstance(page, list) for page in pages):
        rows = [row for page in pages for row in page]
        if not all(isinstance(row, dict) for row in rows):
            raise ValueError("closing PR survey pages must contain objects")
    else:
        # Closing PR pagination validates every slurped page before row access.
        raise ValueError("closing PR survey cannot mix rows and pages")
    closes_issue = re.compile(
        rf"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#{issue}\b",
        re.IGNORECASE,
    )
    for row in rows:
        if not isinstance(row, dict) or not closes_issue.search(
            str(row.get("body") or "")
        ):
            continue
        if row.get("merged_at"):
            return row
        if not merged_only and str(row.get("state") or "").upper() == "OPEN":
            return row
    return None


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
        return {"planned": True, "head": head, "title": title, "number": None}
    url = (result.stdout or "").strip().splitlines()[-1] if result.stdout else ""
    number = _pr_number_from_url(url)
    if number is None:
        # PR creation success requires a recoverable delivery identity.
        raise RuntimeError(
            f"create PR on {repo} succeeded but number is unknown: {url!r}"
        )
    return {"url": url, "head": head, "title": title, "number": number}


def _pr_number_from_url(url: str) -> int | None:
    match = re.search(r"/pull/(\d+)\b", str(url or ""))
    return int(match.group(1)) if match else None


def add_pr_labels(runner: Runner, repo: str, number: int, labels: list[str], *, live: bool) -> None:
    ensure_labels(runner, repo, labels, live=live)
    for label in labels:
        # PR-label mutation failure is not a successful applied atom.
        runner.run_checked(
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
      - pending: checks still running, or GitHub cannot report them yet
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
    # gh: pending checks commonly exit 8. A 429/5xx is also non-green but
    # unknown, not failed CI: wait for an authoritative check read rather than
    # sending a published PR tip through pr_repair.
    if (
        result.timed_out
        or result.returncode == 8
        or "pending" in low
        or "in_progress" in low
        or is_transient_github_text(result.stdout or "", result.stderr or "")
    ):
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
    return gh_json(
        runner,
        [
            "pr",
            "view",
            str(number),
            "--repo",
            repo,
            "--json",
            "number,title,body,comments,commits,statusCheckRollup,headRefName,url",
        ],
        live=live,
        timeout_seconds=60,
    )
