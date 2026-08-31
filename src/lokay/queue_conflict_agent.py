"""Semantic queue-conflict brain: one structured agent call per candidate.

Mechanical covering-PR / branch matches stay deterministic. The agent
judges supersession, epic/child preference, and true path overlap.
"""

from __future__ import annotations

import json
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterable, Mapping

from lokay.agent import run_agent
from lokay.config import Config
from lokay.models import Issue
from lokay.pr_review import PrReviewError, extract_json_object
from lokay.queue_conflict import (
    CLOSE,
    READY,
    SKIP,
    ConflictVerdict,
    evaluate_queue_conflict,
)
from lokay.runner import Runner
from lokay.safety import untrusted_issue_block
from lokay.semantic_trace import SemanticTrace
from lokay.tool_contracts import render_contract
from lokay.stuck import issue_number_from_branch, issue_numbers_covered_by_prs

VALID_OUTCOMES = frozenset({"ready", "skip", "close"})
# These are orchestration facts, not semantic queue evidence. If a harness
# emits one anyway, discard the answer and use the deterministic evaluator.
_POLICY_REASON_MARKERS = (
    "executor",
    "budget",
    "mutex",
    "occup",
    "process",
    "branch",
    "push",
    "merge",
    "test",
)
SEMANTIC_TIMEOUT_SECONDS = 180


class QueueConflictAgentError(ValueError):
    """Invalid structured queue-conflict payload."""


def _as_issue(raw: Issue | Mapping[str, Any]) -> Issue:
    if isinstance(raw, Issue):
        return raw
    return Issue.from_dict(dict(raw))


def covering_pr_numbers(
    issue: Issue,
    open_prs: Iterable[Mapping[str, Any]],
    *,
    branch_prefix: str,
) -> list[int]:
    prs = [dict(p) for p in open_prs if isinstance(p, Mapping)]
    covered = issue_numbers_covered_by_prs(prs, branch_prefix=branch_prefix)
    covering = sorted(
        int(p["number"])
        for p in prs
        if p.get("number") is not None
        and (
            issue_number_from_branch(
                str(p.get("head_ref") or ""), branch_prefix=branch_prefix
            )
            == issue.number
            or issue.number
            in _fixes(f"{p.get('title') or ''}\n{p.get('body') or ''}")
        )
    )
    # ``covered`` is a repo-wide set used by the deterministic evaluator;
    # here we must return only PRs that cover this candidate. Returning every
    # covered issue would make an unrelated PR close the candidate.
    return covering


def _fixes(text: str) -> set[int]:
    from lokay.queue_conflict import fixes_issue_numbers

    return fixes_issue_numbers(text)


def queue_conflict_prompt(
    issue: Issue,
    *,
    open_prs: list[dict[str, Any]],
    peer_issues: list[dict[str, Any]],
) -> str:
    compact_prs = [
        {
            "number": p.get("number"),
            "head_ref": p.get("head_ref") or p.get("headRefName"),
            "title": p.get("title"),
            "body": str(p.get("body") or "")[:400],
        }
        for p in open_prs[:12]
    ]
    compact_peers = [
        {
            "number": p.get("number"),
            "title": p.get("title"),
            "labels": p.get("labels") or [],
            "body": str(p.get("body") or "")[:400],
        }
        for p in peer_issues[:12]
    ]
    return render_contract(
        "queue_conflict",
        candidate=f"{issue.repo}#{issue.number}",
        open_prs=json.dumps(compact_prs, ensure_ascii=False),
        peer_issues=json.dumps(compact_peers, ensure_ascii=False),
        untrusted_issue=untrusted_issue_block(issue.title, issue.body),
    )


def parse_queue_conflict_output(text: str) -> dict[str, Any]:
    data = extract_json_object(text)
    outcome = str(data.get("outcome") or "").strip().lower()
    if outcome not in VALID_OUTCOMES:
        raise QueueConflictAgentError(
            f"outcome must be one of {sorted(VALID_OUTCOMES)}, got {outcome!r}"
        )
    reason = str(data.get("reason") or "agent_queue_conflict").strip() or "agent_queue_conflict"
    detail = data.get("detail") if isinstance(data.get("detail"), dict) else {}
    return {
        "outcome": outcome,
        "reason": reason,
        "detail": detail,
        "summary": str(data.get("summary") or "").strip(),
    }


def _verdict_from_agent(
    parsed: dict[str, Any],
    *,
    issue: Issue,
    ready_label: str,
    tracker_label: str,
) -> ConflictVerdict:
    outcome = parsed["outcome"]
    reason = parsed["reason"]
    detail = dict(parsed["detail"] or {})
    detail.setdefault("issue", issue.number)
    comment = parsed["summary"]
    if outcome == READY:
        return ConflictVerdict(outcome=READY, reason=reason, detail=detail, comment=comment)
    if outcome == SKIP:
        return ConflictVerdict(outcome=SKIP, reason=reason, detail=detail, comment=comment)
    add: list[str] = []
    if "epic" in reason or "tracker" in reason:
        add.append(tracker_label)
    return ConflictVerdict(
        outcome=CLOSE,
        reason=reason,
        detail=detail,
        comment=comment
        or f"Lokay queue-conflict: {reason} for #{issue.number}.",
        remove_labels=[ready_label],
        add_labels=add,
    )


def evaluate_queue_conflict_with_agent(
    candidate: Issue | Mapping[str, Any],
    *,
    runner: Runner | None,
    config: Config | None,
    execute: bool,
    worktree: Path | None = None,
    open_prs: Iterable[Mapping[str, Any]] = (),
    peer_issues: Iterable[Mapping[str, Any]] = (),
    branch_prefix: str = "ai/fix/",
    ready_label: str = "ai:ready",
    tracker_label: str = "ai:tracker",
) -> ConflictVerdict:
    started = time.monotonic()

    def traced(value: ConflictVerdict, source: str, status: str) -> ConflictVerdict:
        trace = SemanticTrace(
            kind="queue",
            source=source,
            status=status,
            duration_ms=round((time.monotonic() - started) * 1000),
            session_kind="queue" if execute else "",
        )
        return replace(value, semantic=trace.to_dict())

    issue = _as_issue(candidate)
    prs = [dict(p) for p in open_prs if isinstance(p, Mapping)]
    peers = [
        dict(p) if isinstance(p, Mapping) else p.to_dict()  # type: ignore[union-attr]
        for p in peer_issues
        if int((p.number if isinstance(p, Issue) else (p.get("number") or -1))) != int(issue.number)
    ]
    covering = covering_pr_numbers(issue, prs, branch_prefix=branch_prefix)
    if covering:
        value = ConflictVerdict(
            outcome=CLOSE,
            reason="open_ai_pr_covers_issue",
            detail={"issue": issue.number, "prs": covering},
            comment=(
                f"Lokay queue-conflict: open AI PR already covers #{issue.number}; "
                f"demoting `{ready_label}` (PR-first)."
            ),
            remove_labels=[ready_label],
        )
        return traced(value, "bypass", "completed")

    fallback = evaluate_queue_conflict(
        issue,
        open_prs=prs,
        peer_issues=peers,
        branch_prefix=branch_prefix,
        ready_label=ready_label,
        tracker_label=tracker_label,
    )
    if not execute or runner is None or config is None:
        return traced(fallback, "fallback", "disabled")

    prompt = queue_conflict_prompt(issue, open_prs=prs, peer_issues=peers)
    cwd = worktree if worktree and Path(worktree).is_dir() else Path.cwd()
    try:
        agent_out = run_agent(
            runner,
            config,
            worktree=cwd,
            prompt=prompt,
            execute=True,
            session_kind="queue",
            timeout_seconds=SEMANTIC_TIMEOUT_SECONDS,
            attach_collector_boundary=False,
        )
    except Exception:  # noqa: BLE001
        return traced(fallback, "fallback", "executor_failed")
    if agent_out.get("status") != "completed":
        status = "timeout" if agent_out.get("status") == "timeout" else "executor_failed"
        return traced(fallback, "fallback", status)
    try:
        parsed = parse_queue_conflict_output(str(agent_out.get("stdout_tail") or ""))
    except (QueueConflictAgentError, PrReviewError):
        return traced(fallback, "fallback", "invalid_json")
    reason_blob = parsed["reason"].lower()
    if any(marker in reason_blob for marker in _POLICY_REASON_MARKERS):
        return traced(fallback, "fallback", "rejected")
    value = _verdict_from_agent(
        parsed,
        issue=issue,
        ready_label=ready_label,
        tracker_label=tracker_label,
    )
    return traced(value, "agent", "completed")
