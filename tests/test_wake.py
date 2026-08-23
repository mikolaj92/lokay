"""Hermetic wake routing (reason → path) + workflow presence."""

from __future__ import annotations


from pathlib import Path

from lokay.proc import wake as wake_proc
from lokay.wake import (
    SKIP_LABELS,
    WAKE_ON_LABELS,
    route_wake,
)

ROOT = Path(__file__).resolve().parents[1]


def test_issue_opened_routes_to_issue_triage():
    plan = route_wake(reason="issue_opened", repo="mikolaj92/lokay", issue=42)
    assert plan.skip is False
    assert plan.path == "issue_triage"
    assert plan.issue == 42
    assert plan.repo == "mikolaj92/lokay"
    assert plan.max_passes is None


def test_issue_labeled_ready_routes_to_issue_triage():
    plan = route_wake(
        reason="issue_labeled",
        repo="a/b",
        issue=7,
        label_name="ai:ready",
        labels=["ai:ready"],
    )
    assert plan.skip is False
    assert plan.path == "issue_triage"
    assert "ai:ready" in WAKE_ON_LABELS


def test_issue_labeled_unrelated_skips():
    plan = route_wake(
        reason="issue_labeled",
        repo="a/b",
        issue=7,
        label_name="documentation",
    )
    assert plan.skip is True
    assert plan.path is None
    assert plan.skip_reason == "label_not_wake:documentation"


def test_spam_label_skips_issue_opened():
    plan = route_wake(
        reason="issue_opened",
        repo="a/b",
        issue=1,
        labels=["spam", "bug"],
    )
    assert plan.skip is True
    assert plan.path is None
    assert "spam" in (plan.skip_reason or "")
    assert "spam" in SKIP_LABELS


def test_checks_with_pr_and_branch_routes_pr_triage():
    plan = route_wake(
        reason="workflow_run",
        repo="a/b",
        pr=9,
        branch="ai/fix/9-thing",
    )
    assert plan.skip is False
    assert plan.path == "pr_triage"
    assert plan.pr == 9
    assert plan.branch == "ai/fix/9-thing"


def test_checks_without_branch_routes_bounded_factory_pass():
    plan = route_wake(reason="checks", repo="a/b", pr=3)
    assert plan.skip is False
    assert plan.path == "factory_pass"
    assert plan.max_passes == 1


def test_check_suite_without_pr_routes_factory_pass():
    plan = route_wake(reason="check_suite", repo="a/b")
    assert plan.path == "factory_pass"
    assert plan.max_passes == 1


def test_factory_reason_bounded():
    plan = route_wake(reason="factory")
    assert plan.skip is False
    assert plan.path == "factory_pass"
    assert plan.max_passes == 1


def test_unknown_reason_skips():
    plan = route_wake(reason="something_else", repo="a/b", issue=1)
    assert plan.skip is True
    assert plan.skip_reason == "unknown_reason:something_else"


def test_issue_requires_number_and_repo():
    assert route_wake(reason="issue", repo="a/b").skip_reason == "issue_required"
    assert route_wake(reason="issue", issue=1).skip_reason == "repo_required"


def test_execute_wake_skip_ok():
    plan = route_wake(reason="issue_labeled", repo="a/b", issue=1, label_name="docs")
    out = wake_proc.execute_wake(plan, config_path=None, live=False)
    assert out["ok"] is True
    assert out["skipped"] is True


def test_github_actions_workflows_are_absent():
    workflows = ROOT / ".github" / "workflows"
    assert not workflows.exists() or not any(workflows.iterdir())
