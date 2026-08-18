"""Atomic: aggregate intake checks → CLOSE | READY | SPLIT | NEEDS_HUMAN + receipt.

Hard facts stay deterministic. Semantic remainder is one structured agent call.
Mutates only with --live.
"""

from __future__ import annotations

import argparse

from lokay.envelope import emit_exit, err, ok
from lokay.gh_issues import get_issue
from lokay.intake import referenced_pr_numbers, should_run_intake
from lokay.intake_agent import decide_intake_with_agent
from lokay.intake_io import apply_intake, covering_ai_prs, merged_prs
from lokay.proc._common import (
    add_config_live,
    semantic_agent_allowed,
    load_cfg,
    mutations_allowed,
    read_live,
    resolve_repo_clone,
    runner,
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-intake-issue")
    add_config_live(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--issue", required=True, type=int)
    p.add_argument("--require-ready", action="store_true", help="implementable only when ready")
    p.add_argument("--candidate-ready", action="store_true", help="upstream triage decided ready")
    p.add_argument("--candidate-split", action="store_true", help="upstream triage decided split")
    args = p.parse_args(argv)
    cfg, r = load_cfg(args), runner()
    live_mut, fetch = mutations_allowed(live_flag=args.live, cfg=cfg), read_live(args)
    try:
        issue = get_issue(r, cfg, args.repo, args.issue, live=fetch)
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    if issue is None:
        return emit_exit(err(f"issue not found: {args.repo}#{args.issue}"))

    run, skip_reason = should_run_intake(
        list(issue.labels or []),
        ready_label=cfg.ready_label,
        needs_feedback_label=cfg.needs_feedback_label,
        blocked_label=cfg.blocked_label,
        candidate_ready=bool(args.candidate_ready),
        candidate_split=bool(args.candidate_split),
    )
    try:
        clone = resolve_repo_clone(cfg, args.repo)
    except KeyError:
        clone = None
    merged: list[int] = []
    covering: list[dict] = []
    if run:
        merged = merged_prs(r, args.repo, referenced_pr_numbers(issue), live=fetch)
        covering = covering_ai_prs(
            r, args.repo, int(args.issue), branch_prefix=cfg.branch_prefix, live=fetch
        )
    decision = decide_intake_with_agent(
        issue,
        runner=r,
        config=cfg,
        execute=semantic_agent_allowed(cfg, live_flag=args.live),
        state=issue.state,
        clone_path=clone,
        merged_prs=merged,
        covering_prs=covering,
        ready_label=cfg.ready_label,
        needs_feedback_label=cfg.needs_feedback_label,
        trusted_assignee=cfg.assignee,
        run=run,
        skip_reason=skip_reason,
        force_split=bool(args.candidate_split) and run,
    )
    try:
        applied = apply_intake(r, cfg, args.repo, int(args.issue), issue, decision, live=live_mut)
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc), decision=decision.to_dict(), issue=issue.to_dict()))

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
