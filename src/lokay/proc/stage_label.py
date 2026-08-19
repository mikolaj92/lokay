"""Atomic: apply one exclusive issue ledger stage (labels + optional receipt)."""

from __future__ import annotations

import argparse

from lokay.envelope import emit_exit, err, ok
from lokay.gh_issues import (
    WORK_READY_LABEL,
    add_issue_labels,
    comment_issue,
    get_issue,
    remove_issue_labels,
)
from lokay.proc._common import add_config_live, load_cfg, mutations_allowed, runner
from lokay.stage_ledger import (
    INFLIGHT_STAGES,
    LABEL_READY,
    STAGES,
    plan_stage_transition,
)


MINI_MILL_REPO = "mikolaj92/lokay"


def _open_issue_removals(
    labels: tuple[str, ...], *, stage: str, ready_label: str
) -> list[str]:
    """Keep readiness while work is in flight; clear may follow a merged PR."""
    if stage not in INFLIGHT_STAGES:
        return list(labels)
    protected = {ready_label, LABEL_READY, WORK_READY_LABEL}
    return [label for label in labels if label not in protected]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-stage-label")
    add_config_live(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--issue", required=True, type=int)
    p.add_argument(
        "--stage",
        required=True,
        choices=sorted(STAGES),
        help="exclusive ledger stage to apply",
    )
    p.add_argument(
        "--receipt",
        action="store_true",
        help="post a short stage receipt comment",
    )
    p.add_argument(
        "--comment",
        default="",
        help="optional comment body (overrides --receipt text when set)",
    )
    args = p.parse_args(argv)
    if args.repo != MINI_MILL_REPO:
        return emit_exit(
            ok(
                planned=not args.live,
                skipped=True,
                reason="repo_not_delivered_by_mini_mill",
                repo=args.repo,
                issue=args.issue,
                stage=args.stage,
                add_labels=[],
                remove_labels=[],
                receipt=False,
                applied=False,
            )
        )
    cfg = load_cfg(args)
    live = mutations_allowed(live_flag=args.live, cfg=cfg)
    try:
        plan = plan_stage_transition(
            args.stage,
            ready_label=str(cfg.ready_label or "ai:ready"),
            receipt=bool(args.receipt),
        )
    except ValueError as exc:
        return emit_exit(err(str(exc)))
    comment = str(args.comment or "").strip() or (plan.receipt or "")
    try:
        issue = get_issue(runner(), cfg, args.repo, args.issue, live=live)
        if issue is None:
            return emit_exit(err(f"issue not found: {args.repo}#{args.issue}"))
        issue_state = str(issue.state or "").upper()
        if issue_state != "OPEN":
            return emit_exit(
                ok(
                    planned=False,
                    repo=args.repo,
                    issue=args.issue,
                    issue_state=issue_state,
                    stage=plan.stage,
                    add_labels=[],
                    remove_labels=[],
                    receipt=False,
                    applied=False,
                    skipped=True,
                    reason="issue_closed",
                )
            )
        remove_labels = _open_issue_removals(
            plan.remove_labels,
            stage=args.stage,
            ready_label=str(cfg.ready_label or LABEL_READY),
        )
        if remove_labels:
            remove_issue_labels(
                runner(), args.repo, args.issue, remove_labels, live=live
            )
        if plan.add_labels:
            add_issue_labels(
                runner(), args.repo, args.issue, list(plan.add_labels), live=live
            )
        if comment:
            comment_issue(runner(), args.repo, args.issue, comment, live=live)
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    return emit_exit(
        ok(
            planned=not live,
            repo=args.repo,
            issue=args.issue,
            stage=plan.stage,
            add_labels=list(plan.add_labels),
            remove_labels=remove_labels,
            receipt=bool(comment),
            applied=live,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
