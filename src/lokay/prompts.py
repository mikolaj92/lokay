from __future__ import annotations

from collections.abc import Iterable

from lokay.localize import render_paths_for_prompt
from lokay.models import Issue
from lokay.safety import untrusted_issue_block
from lokay.tool_contracts import render_contract


def _clip(text: str, limit: int) -> str:
    s = (text or "").strip()
    if len(s) <= limit:
        return s
    return f"{s[:limit]}\n\n[... truncated at {limit} characters]"


_SCOPE_LOCK_MAX = 8


def _scope_block(paths: Iterable[str] | None) -> tuple[str, str]:
    items = [str(p).strip() for p in (paths or []) if str(p).strip()]
    if not items:
        return (
            "",
            "3. Stay inside the localize edit scope when provided; do not roam the whole checkout.",
        )
    rendered = render_paths_for_prompt(items)
    if len(items) <= _SCOPE_LOCK_MAX:
        header = (
            "Edit scope (from semantic `localize` atom, validated by Python):\n"
            "Patch **only** these files/directories. Do not wander the full checkout."
        )
        stay = "3. Stay inside the localize edit scope; do not roam the whole checkout."
    else:
        header = (
            "Edit start (from semantic `localize` atom — hints, not a cage):\n"
            "Start here. Inspect neighbours and tests if the issue needs them."
        )
        stay = "3. Start from the localize hints; add a missing test/module if inspection warrants."
    block = f"""{header}

{rendered}

Localization evidence: read `.lokay/localize.json` if present.
"""
    return block, stay


def issue_fix_prompt(
    issue: Issue, *, branch: str, paths: Iterable[str] | None = None
) -> str:
    """Harness-agnostic goal: implement the issue in this worktree.

    Orchestrator owns branch/commit/push/PR. The coding harness only edits the tree.
    """
    untrusted = untrusted_issue_block(issue.title, issue.body)
    scope, stay = _scope_block(paths)
    return render_contract(
        "issue_fix",
        issue_number=issue.number,
        repo=issue.repo,
        branch=branch,
        issue_url=issue.url,
        scope=scope,
        stay=stay,
        untrusted_issue=untrusted,
    )


def self_repair_prompt(*, issue: Issue, fingerprint: str, evidence: str = "") -> str:
    """Emergency Lokay recovery goal; publication remains deterministic."""
    untrusted = untrusted_issue_block(issue.title, issue.body)
    return render_contract(
        "self_repair",
        fingerprint=fingerprint,
        repo=issue.repo,
        issue_number=issue.number,
        issue_url=issue.url,
        evidence=evidence[:6000] or "(preflight findings only)",
        untrusted_issue=untrusted,
    )


def repair_pr_prompt(
    *,
    repo: str,
    pr_number: int,
    branch: str,
    checks_text: str,
    review_text: str = "",
    paths: Iterable[str] | None = None,
) -> str:
    """Harness-agnostic goal: repair checks or actionable structured review findings."""
    scope, stay = _scope_block(paths)
    return render_contract(
        "pr_repair",
        pr_number=pr_number,
        repo=repo,
        branch=branch,
        checks_text=checks_text[:6000] or "(none)",
        review_text=review_text[:6000] or "(none)",
        scope=scope,
        stay=stay,
    )


def timeout_resume_prompt(
    *,
    repo: str,
    branch: str,
    issue_number: int | None = None,
    issue_title: str = "",
    timeout_seconds: int = 1800,
) -> str:
    """ONE continue pass after the coding slot hit the executor timer."""
    issue_line = (
        f"Issue: #{issue_number} {issue_title}"
        if issue_number is not None
        else "Issue: (unknown)"
    )
    return render_contract(
        "timeout_resume",
        timeout_seconds=timeout_seconds,
        repo=repo,
        branch=branch,
        issue_line=issue_line,
    )


def local_test_repair_prompt(
    *,
    repo: str,
    branch: str,
    issue_number: int | None = None,
    issue_title: str = "",
    log_text: str = "",
) -> str:
    """Harness-agnostic goal: ONE bounded patch after a red local suite.

    AlphaCodium loop, K=1: the failing pytest log drives exactly one repair
    attempt. The orchestrator owns the recheck, push, and any PR — a red
    suite must never reach `gh pr create`.
    """
    issue_line = (
        f"Issue: #{issue_number} {issue_title}"
        if issue_number is not None
        else "Issue: (unknown)"
    )
    return render_contract(
        "local_test_repair",
        repo=repo,
        branch=branch,
        issue_line=issue_line,
        log_text=log_text[:6000] or "(no log captured)",
    )


def pr_body(issue: Issue, *, agent_summary: str, incident_fingerprint: str = "") -> str:
    linkage = (
        f"Refs #{issue.number}" if incident_fingerprint else f"Closes #{issue.number}"
    )
    marker = (
        f"<!-- lokay-preflight:{incident_fingerprint} -->\n"
        if incident_fingerprint
        else ""
    )
    # PR review receives the ticket body, not only the builder's summary.
    return f"""{marker}## Summary

Automated Lokay fix for {issue.repo}#{issue.number}.

{linkage}

## Issue

{issue.title}

## Ticket evidence

{_clip(issue.body or "(no ticket body)", 8000)}

## Agent notes

{_clip(agent_summary or "(no summary)", 4000)}

## Test evidence

See agent notes above for commands run. Orchestrator requires visible test evidence before merge when enabled.

## Labels

- ai:generated
- ai:pr-opened
"""
