"""Atomic: aggregate intake checks → CLOSE | READY | SPLIT | NEEDS_HUMAN + receipt.

Hardens triage / ready issues before `issue_to_pr`. Mutates only with --live.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from lokay.envelope import emit_exit, err, ok
from lokay.gh_issues import (
    add_issue_labels,
    assign_issue,
    close_issue,
    comment_issue,
    get_issue,
    remove_issue_labels,
)
from lokay.intake import decide_intake, referenced_pr_numbers
from lokay.proc._common import (
    add_config_live,
    load_cfg,
    mutations_allowed,
    resolve_repo_clone,
    runner,
)
from lokay.runner import gh_spec
from lokay.stuck import issue_number_from_branch
from lokay.triage import is_parked, is_undecided


def _fetch_live() -> bool:
    return os.environ.get("LOKAY_OFFLINE", "").strip() not in {"1", "true", "yes"}


def _merged_prs(repo: str, numbers: list[int], *, live: bool) -> list[int]:
    """Return which of the referenced PRs are merged (best-effort)."""
    if not live or not numbers:
        return []
    merged: list[int] = []
    r = runner()
    for num in numbers:
        result = r.run(
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


def _covering_ai_prs(
    repo: str,
    issue_number: int,
    *,
    branch_prefix: str,
    live: bool,
) -> list[dict]:
    """Open or recently merged ai/fix PRs whose branch embeds this issue number."""
    if not live:
        return []
    r = runner()
    prefix = branch_prefix.rstrip("/") + "/"
    out: list[dict] = []
    for state in ("open", "merged"):
        result = r.run(
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
                    "50",
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
    # de-dupe by number
    seen: set[int] = set()
    uniq: list[dict] = []
    for row in out:
        n = int(row["number"])
        if n in seen or n <= 0:
            continue
        seen.add(n)
        uniq.append(row)
    return uniq


def _should_run_intake(
    issue_labels: list[str],
    *,
    ready_label: str,
    needs_feedback_label: str,
    blocked_label: str,
    candidate_ready: bool = False,
    candidate_split: bool = False,
) -> tuple[bool, str]:
    """Intake runs for ready/split candidates; skips parked / undecided / human-parked."""
    if is_parked(issue_labels):
        return False, "parked_frozen"
    labels = set(issue_labels)
    if ready_label in labels:
        return True, "already_ready"
    if candidate_split:
        return True, "triage_split_candidate"
    if candidate_ready:
        # Upstream triage decided ready (including dry-run where labels are not applied).
        return True, "triage_ready_candidate"
    if blocked_label in labels:
        return False, "blocked"
    if needs_feedback_label in labels:
        return False, "needs_feedback"
    # Undecided inbox: triage_issue should have run first in issue_triage.
    # If somehow still undecided, skip (do not READY from intake alone).
    if is_undecided(
        issue_labels,
        ready_label=ready_label,
        blocked_label=blocked_label,
        needs_feedback_label=needs_feedback_label,
    ):
        return False, "undecided_await_triage"
    return False, "not_ready_candidate"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-intake-issue")
    add_config_live(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--issue", required=True, type=int)
    p.add_argument(
        "--require-ready",
        action="store_true",
        help="implement gate: only implementable when decision=ready",
    )
    p.add_argument(
        "--candidate-ready",
        action="store_true",
        help="upstream triage decided ready (label may not be applied yet)",
    )
    p.add_argument(
        "--candidate-split",
        action="store_true",
        help="upstream triage decided oversized work should auto-split",
    )
    args = p.parse_args(argv)
    cfg = load_cfg(args)
    live_mut = mutations_allowed(live_flag=args.live, cfg=cfg)
    fetch = _fetch_live()
    try:
        issue = get_issue(runner(), cfg, args.repo, args.issue, live=fetch)
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    if issue is None:
        return emit_exit(err(f"issue not found: {args.repo}#{args.issue}"))

    run, skip_reason = _should_run_intake(
        list(issue.labels or []),
        ready_label=cfg.ready_label,
        needs_feedback_label=cfg.needs_feedback_label,
        blocked_label=cfg.blocked_label,
        candidate_ready=bool(args.candidate_ready),
        candidate_split=bool(args.candidate_split),
    )

    clone: Path | None
    try:
        clone = resolve_repo_clone(cfg, args.repo)
    except KeyError:
        clone = None

    merged: list[int] = []
    covering: list[dict] = []
    if run:
        merged = _merged_prs(args.repo, referenced_pr_numbers(issue), live=fetch)
        covering = _covering_ai_prs(
            args.repo,
            int(args.issue),
            branch_prefix=cfg.branch_prefix,
            live=fetch,
        )

    decision = decide_intake(
        issue,
        state=issue.state,
        clone_path=clone,
        merged_prs=merged,
        covering_prs=covering,
        ready_label=cfg.ready_label,
        needs_feedback_label=cfg.needs_feedback_label,
        run=run,
        skip_reason=skip_reason,
        force_split=bool(args.candidate_split) and run,
    )

    applied = False
    if live_mut and decision.decision not in {"skip", "ready"}:
        try:
            if decision.remove_labels:
                to_remove = [x for x in decision.remove_labels if x in (issue.labels or [])]
                if to_remove:
                    remove_issue_labels(runner(), args.repo, args.issue, to_remove, live=True)
            if decision.add_labels:
                add_issue_labels(
                    runner(),
                    args.repo,
                    args.issue,
                    list(decision.add_labels),
                    live=True,
                )
            # Split receipts are finalized by issue_split; still drop ready + short note.
            if decision.comment and decision.decision != "split":
                comment_issue(runner(), args.repo, args.issue, decision.comment, live=True)
            elif decision.decision == "split" and decision.comment:
                comment_issue(runner(), args.repo, args.issue, decision.comment, live=True)
            if decision.close and (issue.state or "OPEN").upper() == "OPEN":
                close_issue(runner(), args.repo, args.issue, live=True)
            applied = True
        except Exception as exc:  # noqa: BLE001
            return emit_exit(
                err(
                    str(exc),
                    decision=decision.to_dict(),
                    issue=issue.to_dict(),
                )
            )
    elif live_mut and decision.decision == "ready":
        # Confirm ready path: ensure label + assignee (idempotent).
        try:
            if cfg.ready_label not in (issue.labels or []):
                add_issue_labels(
                    runner(),
                    args.repo,
                    args.issue,
                    [cfg.ready_label],
                    live=True,
                )
                applied = True
            if cfg.assignee and cfg.assignee not in (issue.assignees or []):
                assign_issue(runner(), cfg, args.repo, args.issue, live=True)
                applied = True
        except Exception as exc:  # noqa: BLE001
            return emit_exit(
                err(
                    str(exc),
                    decision=decision.to_dict(),
                    issue=issue.to_dict(),
                )
            )

    implementable = bool(decision.implementable and decision.decision == "ready")
    if args.require_ready and not implementable and decision.decision != "skip":
        implementable = False

    return emit_exit(
        ok(
            planned=not live_mut,
            applied=applied,
            repo=args.repo,
            issue=issue.to_dict(),
            decision=decision.to_dict(),
            implementable=implementable,
            require_ready=bool(args.require_ready),
            skipped=decision.decision == "skip",
            reason=decision.reason,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
