"""GitHub I/O for structured PR review. Not a review brain."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from lokay.config import Config
from lokay.gh_issues import ensure_labels
from lokay.gh_prs import add_pr_labels, comment_bodies, comment_pr, gh_json, gh_text
from lokay.pr_review import PrReviewDecision, build_review_comment_body, labels_for_review
from lokay.runner import Runner

FAIL_CLOSED = (
    "Lokay LLM PR review failed closed (invalid structured output): {exc}\n"
    "Will not auto-merge until a valid review is produced."
)
_VIEW_FIELDS = "number,title,body,headRefName,headRefOid,url,isDraft,mergeable,comments"


def load_pr_evidence(
    runner: Runner,
    repo: str,
    pr: int,
    *,
    live: bool,
    branch: str = "",
    checks_text: str = "",
) -> dict[str, Any]:
    view = gh_json(
        runner,
        ["pr", "view", str(pr), "--repo", repo, "--json", _VIEW_FIELDS],
        live=live,
    )
    # PR review refuses to substitute a GitHub error for the code diff.
    diff = gh_text(
        runner,
        ["pr", "diff", str(pr), "--repo", repo],
        live=live,
        require_success=True,
    )
    if not checks_text and live:
        checks_text = gh_text(
            runner, ["pr", "checks", str(pr), "--repo", repo], live=live
        )
    return {
        "title": str(view.get("title") or ""),
        "body": str(view.get("body") or ""),
        "head": str(branch or view.get("headRefName") or ""),
        "head_sha": str(view.get("headRefOid") or "").strip().lower(),
        "comments": comment_bodies(view),
        "diff": diff,
        "checks_text": checks_text,
    }


def review_worktree(cfg: Config, repo: str) -> Path | None:
    """Return the review directory, or skip repos outside this mini mill."""
    try:
        worktree = next(r.clone_path for r in cfg.repos if r.name == repo)
        if not worktree.is_dir():
            raise KeyError(repo)
    except Exception:
        worktree = Path(tempfile.mkdtemp(prefix="lokay-pr-review-"))
    return worktree


def publish_review(
    runner: Runner,
    repo: str,
    pr: int,
    body: str,
    labels: list[str],
    *,
    live: bool,
) -> None:
    comment_pr(runner, repo, pr, body, live=live)
    if labels:
        ensure_labels(runner, repo, labels, live=live)
        add_pr_labels(runner, repo, pr, labels, live=live)


def publish_fail_closed(
    runner: Runner, repo: str, pr: int, exc: Exception, *, mutate: bool
) -> bool:
    if not mutate:
        return False
    try:
        publish_review(
            runner, repo, pr, FAIL_CLOSED.format(exc=exc), ["ai:needs-review"], live=True
        )
        return True
    except Exception:
        return False


def publish_decision(
    runner: Runner,
    repo: str,
    pr: int,
    decision: PrReviewDecision,
    *,
    head_sha: str,
    merge_ok: bool,
    escalated: bool,
    mutate: bool,
) -> None:
    if not mutate:
        return
    publish_review(
        runner,
        repo,
        pr,
        build_review_comment_body(
            decision, head_sha=head_sha, merge_ok=merge_ok, escalated=escalated
        ),
        labels_for_review(decision, escalated=escalated),
        live=True,
    )
