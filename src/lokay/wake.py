"""Event-wake routing: GitHub reason → bounded Fala/mill path.

Pure policy for ``lokay-wake``. Interprets issue / PR / checks wakes and picks
``issue_triage``, ``pr_triage``, or bounded ``factory_pass`` (max-passes 1).
Serial by design — does not start a parallel coding fleet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

WakePath = Literal["issue_triage", "pr_triage", "factory_pass"]

# Skip wakes that are clearly noise / closed-shape (not intentional work).
SKIP_LABELS = frozenset({"spam", "invalid", "wontfix"})

# For ``issues: labeled`` — only these labels should wake the mill.
WAKE_ON_LABELS = frozenset({"ai:ready"})

ISSUE_REASONS = frozenset(
    {
        "issue",
        "issue_opened",
        "issue_labeled",
        "issues",
    }
)
PR_CHECK_REASONS = frozenset(
    {
        "pr",
        "checks",
        "check_suite",
        "check_run",
        "workflow_run",
        "pr_checks",
    }
)
FACTORY_REASONS = frozenset(
    {
        "factory",
        "factory_pass",
        "mill",
        "tick",
    }
)


@dataclass(frozen=True)
class WakePlan:
    """One wake decision (path + targets). ``skip`` means no mill work."""

    path: WakePath | None
    reason: str
    repo: str | None
    issue: int | None
    pr: int | None
    branch: str | None
    max_passes: int | None
    skip: bool
    skip_reason: str | None = None

    def as_dict(self) -> dict:
        return {
            "path": self.path,
            "reason": self.reason,
            "repo": self.repo,
            "issue": self.issue,
            "pr": self.pr,
            "branch": self.branch,
            "max_passes": self.max_passes,
            "skip": self.skip,
            "skip_reason": self.skip_reason,
        }


def _norm_reason(reason: str) -> str:
    return str(reason or "").strip().lower().replace("-", "_")


def _label_set(labels: list[str] | None) -> set[str]:
    out: set[str] = set()
    for item in labels or []:
        name = str(item or "").strip()
        if name:
            out.add(name)
    return out


def route_wake(
    *,
    reason: str,
    repo: str | None = None,
    issue: int | None = None,
    pr: int | None = None,
    branch: str | None = None,
    labels: list[str] | None = None,
    label_name: str | None = None,
) -> WakePlan:
    """Map a wake reason to a bounded path (or skip).

    Routing:
    - issue opened / labeled (relevant) → ``issue_triage``
    - PR / checks with pr+branch → ``pr_triage``
    - PR / checks without branch → bounded ``factory_pass``
    - factory / mill / tick → bounded ``factory_pass``
    """
    norm = _norm_reason(reason)
    repo_s = str(repo or "").strip() or None
    branch_s = str(branch or "").strip() or None
    label_names = _label_set(labels)
    if label_name:
        label_names.add(str(label_name).strip())

    skipped = label_names & SKIP_LABELS
    if skipped:
        return WakePlan(
            path=None,
            reason=norm or reason,
            repo=repo_s,
            issue=issue,
            pr=pr,
            branch=branch_s,
            max_passes=None,
            skip=True,
            skip_reason=f"skip_labels:{','.join(sorted(skipped))}",
        )

    if not norm:
        return WakePlan(
            path=None,
            reason=reason,
            repo=repo_s,
            issue=issue,
            pr=pr,
            branch=branch_s,
            max_passes=None,
            skip=True,
            skip_reason="missing_reason",
        )

    if norm in {"issue_labeled", "labeled"} or (
        norm in ISSUE_REASONS and label_name and norm != "issue_opened"
    ):
        # Labeled events: only wake on intentional ready (or explicit wake labels).
        wake_label = str(label_name or "").strip()
        if wake_label and wake_label not in WAKE_ON_LABELS:
            return WakePlan(
                path=None,
                reason=norm,
                repo=repo_s,
                issue=issue,
                pr=pr,
                branch=branch_s,
                max_passes=None,
                skip=True,
                skip_reason=f"label_not_wake:{wake_label}",
            )

    if norm in ISSUE_REASONS or norm == "labeled":
        if issue is None:
            return WakePlan(
                path=None,
                reason=norm,
                repo=repo_s,
                issue=None,
                pr=pr,
                branch=branch_s,
                max_passes=None,
                skip=True,
                skip_reason="issue_required",
            )
        if not repo_s:
            return WakePlan(
                path=None,
                reason=norm,
                repo=None,
                issue=issue,
                pr=pr,
                branch=branch_s,
                max_passes=None,
                skip=True,
                skip_reason="repo_required",
            )
        return WakePlan(
            path="issue_triage",
            reason=norm,
            repo=repo_s,
            issue=int(issue),
            pr=None,
            branch=None,
            max_passes=None,
            skip=False,
        )

    if norm in PR_CHECK_REASONS:
        if repo_s and pr is not None and branch_s:
            return WakePlan(
                path="pr_triage",
                reason=norm,
                repo=repo_s,
                issue=None,
                pr=int(pr),
                branch=branch_s,
                max_passes=None,
                skip=False,
            )
        # No PR head yet (fork / incomplete payload) — survey + closeout via one pass.
        return WakePlan(
            path="factory_pass",
            reason=norm,
            repo=repo_s,
            issue=None,
            pr=int(pr) if pr is not None else None,
            branch=branch_s,
            max_passes=1,
            skip=False,
        )

    if norm in FACTORY_REASONS:
        return WakePlan(
            path="factory_pass",
            reason=norm,
            repo=repo_s,
            issue=issue,
            pr=pr,
            branch=branch_s,
            max_passes=1,
            skip=False,
        )

    return WakePlan(
        path=None,
        reason=norm,
        repo=repo_s,
        issue=issue,
        pr=pr,
        branch=branch_s,
        max_passes=None,
        skip=True,
        skip_reason=f"unknown_reason:{norm}",
    )
