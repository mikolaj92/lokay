"""Atomic: decide + apply triage labels/comment/close for one issue.

Uses pure lokay.triage.decide_issue; mutates only with --live.
"""

from __future__ import annotations

import argparse
import os

from lokay.envelope import emit_exit, err, ok
from lokay.gh_issues import (
    add_issue_labels,
    assign_issue,
    close_issue,
    comment_issue,
    get_issue,
)
from lokay.proc._common import add_config_live, load_cfg, mutations_allowed, runner
from lokay.triage import decide_issue




def _fetch_live() -> bool:
    return os.environ.get("LOKAY_OFFLINE", "").strip() not in {"1", "true", "yes"}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-triage-issue")
    add_config_live(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--issue", required=True, type=int)
    args = p.parse_args(argv)
    cfg = load_cfg(args)
    live_mut = mutations_allowed(live_flag=args.live, cfg=cfg)
    try:
        issue = get_issue(runner(), cfg, args.repo, args.issue, live=_fetch_live())
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    if issue is None:
        return emit_exit(err(f"issue not found: {args.repo}#{args.issue}"))

    decision = decide_issue(
        issue,
        ready_label=cfg.ready_label,
        blocked_label=cfg.blocked_label,
        needs_feedback_label=cfg.needs_feedback_label,
    )
    applied = False
    if live_mut and decision.decision != "skip":
        try:
            if decision.add_labels:
                add_issue_labels(
                    runner(),
                    args.repo,
                    args.issue,
                    list(decision.add_labels),
                    live=True,
                )
            # Ready without assignee is invisible under allow_unassigned=false.
            if decision.decision == "ready" and cfg.assignee:
                assign_issue(runner(), cfg, args.repo, args.issue, live=True)
            if decision.comment:
                comment_issue(runner(), args.repo, args.issue, decision.comment, live=True)
            if decision.close:
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

    return emit_exit(
        ok(
            planned=not live_mut,
            applied=applied,
            repo=args.repo,
            issue=issue.to_dict(),
            decision=decision.to_dict(),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
