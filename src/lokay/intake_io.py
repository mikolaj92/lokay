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
from lokay.gh_rate import survey_list_cap
from lokay.intake import IntakeDecision
from lokay.models import Issue
from lokay.runner import Runner, gh_spec
from lokay.stuck import issue_number_from_branch


def merged_prs(runner: Runner, repo: str, numbers: list[int], *, live: bool) -> list[int]:
    """Return which of the referenced PRs are merged (best-effort)."""
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
            continue
        try:
            row = json.loads(result.stdout or "{}")
        except json.JSONDecodeError:
            continue
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
    """Open or recently merged ai/fix PRs whose branch embeds this issue number."""
    if not live:
        return []
    prefix = branch_prefix.rstrip("/") + "/"
    out: list[dict[str, Any]] = []
    for state in ("open", "merged"):
        result = runner.run(
            gh_spec(
                [
                    "pr",
                    "list",
                    "--repo",
                    repo,
                    "--state",
                    state,
                    "--json",
                    "number,state,mergedAt,headRefName",
                    "--limit",
                    str(survey_list_cap()),
                ],
                timeout_seconds=60,
            ),
            live=True,
        )
        if result.returncode != 0:
            continue
        try:
            rows = json.loads(result.stdout or "[]")
        except json.JSONDecodeError:
            continue
        for row in rows:
            head = str(row.get("headRefName") or "")
            if not head.startswith(prefix):
                continue
            covered = issue_number_from_branch(head, branch_prefix=branch_prefix)
            if covered != int(issue_number):
                continue
            out.append(
                {
                    "number": int(row.get("number") or 0),
                    "state": str(row.get("state") or state).upper(),
                    "merged": bool(row.get("mergedAt")) or state == "merged",
                    "head_ref": head,
                }
            )
    seen: set[int] = set()
    uniq: list[dict[str, Any]] = []
    for row in out:
        n = int(row["number"])
        if n in seen or n <= 0:
            continue
        seen.add(n)
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
