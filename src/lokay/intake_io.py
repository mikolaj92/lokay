"""GitHub I/O for intake evidence + mutation. Not an intake brain."""

from __future__ import annotations

import json
from typing import Any

from lokay.config import Config
from lokay.gh_issues import (
    WORK_READY_LABEL,
    add_issue_labels,
    assign_issue,
    close_issue,
    comment_issue,
    remove_issue_labels,
)
from lokay.intake import IntakeDecision
from lokay.models import Issue
from lokay.runner import Runner, gh_spec
from lokay.stuck import issue_number_from_branch

COVERING_PR_PAGE_SIZE = 100


def merged_prs(runner: Runner, repo: str, numbers: list[int], *, live: bool) -> list[int]:
    """Return merged referenced PRs; unavailable evidence fails closed."""
    if not live or not numbers:
        return []
    merged: list[int] = []
    for num in numbers:
        result = runner.run(
            gh_spec(
                [
                    "pr",
                    "view",
                    str(num),
                    "--repo",
                    repo,
                    "--json",
                    "state,mergedAt,number",
                ],
                timeout_seconds=60,
            ),
            live=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"intake linked PR #{num} probe failed for {repo}")
        try:
            row = json.loads(result.stdout or "{}")
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"intake linked PR #{num} probe returned malformed JSON for {repo}"
            ) from exc
        if not isinstance(row, dict):
            raise RuntimeError(
                f"intake linked PR #{num} probe returned non-object JSON for {repo}"
            )
        # Intake linked-PR uncertainty is not an unmerged verdict.
        state = str(row.get("state") or "").upper()
        if row.get("mergedAt") or state == "MERGED":
            merged.append(int(row.get("number") or num))
    return merged


def covering_ai_prs(
    runner: Runner,
    repo: str,
    issue_number: int,
    *,
    branch_prefix: str,
    live: bool,
) -> list[dict[str, Any]]:
    """Return complete covering-PR evidence without scanning ancient history.

    GitHub issues and pull requests share one monotonically increasing number
    sequence inside a repository. A PR created for an issue must therefore have
    a larger number. Read the unified PR history newest-first and stop only when
    a page crosses the issue number. Unlike ``gh pr list --limit``, a full page
    is not treated as an unexplained truncation.
    """
    if not live:
        return []
    prefix = branch_prefix.rstrip("/") + "/"
    target = int(issue_number)
    per_page = COVERING_PR_PAGE_SIZE
    page = 1
    out: list[dict[str, Any]] = []
    while True:
        result = runner.run(
            gh_spec(
                [
                    "api",
                    "--method",
                    "GET",
                    f"repos/{repo}/pulls",
                    "-f",
                    "state=all",
                    "-f",
                    "sort=created",
                    "-f",
                    "direction=desc",
                    "-f",
                    f"per_page={per_page}",
                    "-f",
                    f"page={page}",
                ],
                timeout_seconds=60,
            ),
            live=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"intake covering PR page {page} probe failed for {repo}")
        try:
            rows = json.loads(result.stdout or "[]")
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"intake covering PR page {page} returned malformed JSON for {repo}"
            ) from exc
        if not isinstance(rows, list):
            raise ValueError(
                f"intake covering PR page {page} must be a JSON list for {repo}"
            )
        if not all(isinstance(row, dict) for row in rows):
            raise ValueError(
                f"intake covering PR page {page} must contain objects for {repo}"
            )
        crossed_boundary = False
        for row in rows:
            try:
                number = int(row["number"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"intake covering PR page {page} has invalid PR identity for {repo}"
                ) from exc
            if number <= target:
                crossed_boundary = True
                continue
            head_obj = row.get("head")
            if not isinstance(head_obj, dict):
                raise ValueError(
                    f"intake covering PR page {page} has invalid head evidence for {repo}"
                )
            head = str(head_obj.get("ref") or "")
            if not head.startswith(prefix):
                continue
            covered = issue_number_from_branch(head, branch_prefix=branch_prefix)
            if covered != target:
                continue
            state = str(row.get("state") or "").upper()
            merged_at = row.get("merged_at")
            out.append(
                {
                    "number": number,
                    "state": "MERGED" if merged_at else state,
                    "merged": bool(merged_at),
                    "head_ref": head,
                }
            )
        if crossed_boundary or len(rows) < per_page:
            break
        page += 1

    seen: set[int] = set()
    uniq: list[dict[str, Any]] = []
    for row in out:
        number = int(row["number"])
        if number in seen:
            continue
        seen.add(number)
        uniq.append(row)
    return uniq


def apply_intake(
    runner: Runner,
    cfg: Config,
    repo: str,
    issue_number: int,
    issue: Issue,
    decision: IntakeDecision,
    *,
    live: bool,
) -> bool:
    """Apply intake labels / comment / close. Mutates only when live."""
    if not live or decision.decision == "skip":
        return False
    if decision.decision == "blocked":
        applied = False
        if decision.remove_labels:
            to_remove = [x for x in decision.remove_labels if x in (issue.labels or [])]
            if to_remove:
                remove_issue_labels(runner, repo, issue_number, to_remove, live=True)
                applied = True
        if decision.add_labels:
            add_issue_labels(runner, repo, issue_number, list(decision.add_labels), live=True)
            applied = True
        if decision.comment:
            comment_issue(runner, repo, issue_number, decision.comment, live=True)
            applied = True
        return applied
    if decision.decision == "ready":
        applied = False
        have = set(issue.labels or [])
        wanted: list[str] = []
        for label in (cfg.ready_label, WORK_READY_LABEL, *decision.add_labels):
            if label and label not in wanted:
                wanted.append(label)
        to_add = [label for label in wanted if label not in have]
        if to_add:
            add_issue_labels(runner, repo, issue_number, to_add, live=True)
            applied = True
        if cfg.assignee and cfg.assignee not in (issue.assignees or []):
            assign_issue(runner, cfg, repo, issue_number, live=True)
            applied = True
        return applied
    if decision.remove_labels:
        to_remove = [x for x in decision.remove_labels if x in (issue.labels or [])]
        if to_remove:
            remove_issue_labels(runner, repo, issue_number, to_remove, live=True)
    if decision.add_labels:
        add_issue_labels(runner, repo, issue_number, list(decision.add_labels), live=True)
    if decision.comment:
        comment_issue(runner, repo, issue_number, decision.comment, live=True)
    if decision.close and (issue.state or "OPEN").upper() == "OPEN":
        close_issue(runner, repo, issue_number, live=True)
    return True
