"""Atomic: auto-split oversized issue into bounded child issues (gh + rules).

Runs after intake when decision=split. No coding agent. Fail closed → needs-human
when a deterministic child plan cannot be built.
"""

from __future__ import annotations

import argparse
import json
import os

from lokay.envelope import emit_exit, err, ok
from lokay.gh_issues import (
    add_issue_labels,
    close_issue,
    comment_issue,
    create_issue,
    get_issue,
    remove_issue_labels,
)
from lokay.proc._common import add_config_live, load_cfg, mutations_allowed, runner
from lokay.issue_checkboxes import is_bug_issue
from lokay.split import parent_tracker_comment, plan_split


def _fetch_live() -> bool:
    return os.environ.get("LOKAY_OFFLINE", "").strip() not in {"1", "true", "yes"}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-issue-split")
    add_config_live(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--issue", required=True, type=int)
    p.add_argument(
        "--reason",
        default="",
        help="intake/triage split reason (optional)",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="split even when intake decision was not split (tests / recovery)",
    )
    p.add_argument(
        "--intake-decision",
        default="",
        help="upstream intake decision JSON or bare decision string",
    )
    args = p.parse_args(argv)
    cfg = load_cfg(args)
    live_mut = mutations_allowed(live_flag=args.live, cfg=cfg)
    fetch = _fetch_live()

    decision_name = ""
    reason = str(args.reason or "").strip()
    raw = str(args.intake_decision or "").strip()
    if raw:
        if raw.startswith("{"):
            try:
                blob = json.loads(raw)
            except json.JSONDecodeError:
                blob = {}
            if isinstance(blob, dict):
                decision_name = str(blob.get("decision") or "")
                reason = reason or str(blob.get("reason") or "")
        else:
            decision_name = raw

    should_split = bool(args.force) or decision_name == "split" or reason in {
        "too_large_split",
        "inventory_everything",
        "multi_epic_blob",
        "too_many_checkboxes",
        "triage_split_candidate",
    }
    if not should_split:
        return emit_exit(
            ok(
                planned=not live_mut,
                applied=False,
                skipped=True,
                reason=f"not_split_decision:{decision_name or 'none'}",
                repo=args.repo,
                issue=int(args.issue),
                children=[],
            )
        )

    try:
        issue = get_issue(runner(), cfg, args.repo, args.issue, live=fetch)
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    if issue is None:
        return emit_exit(err(f"issue not found: {args.repo}#{args.issue}"))

    # Skip when already a tracker / closed.
    if "ai:tracker" in (issue.labels or []):
        return emit_exit(
            ok(
                planned=not live_mut,
                applied=False,
                skipped=True,
                reason="already_tracker",
                repo=args.repo,
                issue=issue.to_dict(),
                children=[],
            )
        )
    if (issue.state or "OPEN").upper() != "OPEN" and not args.force:
        return emit_exit(
            ok(
                planned=not live_mut,
                applied=False,
                skipped=True,
                reason="parent_not_open",
                repo=args.repo,
                issue=issue.to_dict(),
                children=[],
            )
        )

    if is_bug_issue(issue) and (reason or "too_large_split") in {
        "too_many_checkboxes",
        "too_large_split",
    }:
        return emit_exit(
            ok(
                planned=not live_mut,
                applied=False,
                skipped=True,
                reason="bug_is_not_an_epic",
                repo=args.repo,
                issue=issue.to_dict(),
                children=[],
            )
        )

    plan = plan_split(issue, reason=reason or "too_large_split")
    if plan is None:
        # Fail closed: residual human mailbox — not READY.
        applied = False
        if live_mut:
            try:
                add_issue_labels(
                    runner(),
                    args.repo,
                    args.issue,
                    [cfg.needs_feedback_label],
                    live=True,
                )
                if cfg.ready_label in (issue.labels or []):
                    remove_issue_labels(
                        runner(),
                        args.repo,
                        args.issue,
                        [cfg.ready_label],
                        live=True,
                    )
                comment_issue(
                    runner(),
                    args.repo,
                    args.issue,
                    "Needs feedback (rare): auto-split could not extract child parts. "
                    "File smaller issues or add checkbox slices, then remove this label.",
                    live=True,
                )
                applied = True
            except Exception as exc:  # noqa: BLE001
                return emit_exit(err(str(exc), issue=issue.to_dict()))
        return emit_exit(
            ok(
                planned=not live_mut,
                applied=applied,
                skipped=False,
                reason="split_impossible",
                decision="needs_human",
                repo=args.repo,
                issue=issue.to_dict(),
                children=[],
                plan=None,
            )
        )

    children_out: list[dict] = []
    applied = False
    if live_mut:
        try:
            for child in plan.children:
                created = create_issue(
                    runner(),
                    repo=args.repo,
                    title=child.title,
                    body=child.body,
                    labels=[],
                    live=True,
                )
                children_out.append({**child.to_dict(), **created})
            child_nums = [int(c["number"]) for c in children_out if c.get("number")]
            if plan.demote_parent:
                if cfg.ready_label in (issue.labels or []):
                    remove_issue_labels(
                        runner(),
                        args.repo,
                        args.issue,
                        [cfg.ready_label],
                        live=True,
                    )
                if cfg.needs_feedback_label in (issue.labels or []):
                    remove_issue_labels(
                        runner(),
                        args.repo,
                        args.issue,
                        [cfg.needs_feedback_label],
                        live=True,
                    )
                add_issue_labels(
                    runner(),
                    args.repo,
                    args.issue,
                    [plan.parent_tracker_label],
                    live=True,
                )
            comment_issue(
                runner(),
                args.repo,
                args.issue,
                parent_tracker_comment(plan, child_nums),
                live=True,
            )
            if plan.close_parent and (issue.state or "OPEN").upper() == "OPEN":
                close_issue(runner(), args.repo, args.issue, live=True)
            applied = True
        except Exception as exc:  # noqa: BLE001
            return emit_exit(
                err(
                    str(exc),
                    issue=issue.to_dict(),
                    plan=plan.to_dict(),
                    children=children_out,
                )
            )
    else:
        children_out = [c.to_dict() for c in plan.children]

    return emit_exit(
        ok(
            planned=not live_mut,
            applied=applied,
            skipped=False,
            reason=plan.reason,
            decision="split",
            repo=args.repo,
            issue=issue.to_dict(),
            plan=plan.to_dict(),
            children=children_out,
            parent_tracker=True,
            parent_closed=bool(plan.close_parent),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
