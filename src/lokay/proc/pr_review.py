"""Atomic: LLM structured review of an AI PR (configured executor). Fail closed on bad JSON."""

from __future__ import annotations

import argparse

from lokay.agent import run_agent
from lokay.envelope import emit_exit, err, ok
from lokay.pr_review import (
    PrReviewError,
    coerce_soft_nits,
    count_request_changes_reviews,
    decide_review_merge,
    find_review_for_head,
    parse_review_markers,
    parse_review_output,
    review_prompt,
)
from lokay.pr_review_io import load_pr_evidence, publish_decision, publish_fail_closed, review_worktree
from lokay.proc._common import add_config_live, agent_execute_allowed, load_cfg, mutations_allowed, runner


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-pr-review")
    add_config_live(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--pr", required=True, type=int)
    p.add_argument("--branch", default="")
    p.add_argument("--checks-text", default="", help="optional CI text; otherwise re-fetched lightly via pr view")
    args = p.parse_args(argv)
    cfg, live, r = load_cfg(args), bool(args.live), runner()
    execute = agent_execute_allowed(cfg, live_flag=args.live)
    if live and cfg.mode != "live":
        return emit_exit(err("refusing live pr_review while config mode is not live"))
    if not cfg.executor_enabled:
        return emit_exit(ok(offline=not live, skipped=True, reason="executor_disabled",
                            repo=args.repo, pr=args.pr, merge_ok=False))

    ev = load_pr_evidence(r, args.repo, int(args.pr), live=live,
                          branch=args.branch, checks_text=args.checks_text)
    head, head_sha = ev["head"], ev["head_sha"]
    markers = parse_review_markers(ev["comments"])
    prior = find_review_for_head(markers, head_sha)
    prior_rc = count_request_changes_reviews(markers)
    max_rc = max(1, int(getattr(cfg, "max_request_changes_per_pr", 2)))
    if live and head_sha and prior is not None:
        return emit_exit(ok(offline=False, skipped=True, reason="already_reviewed_head",
                            repo=args.repo, pr=args.pr, branch=head, head_sha=head_sha,
                            decision={"verdict": str(prior.get("verdict") or "")},
                            merge_ok=bool(prior.get("merge_ok")), applied=False,
                            request_changes_count=prior_rc))

    prompt = review_prompt(
        repo=args.repo, pr_number=int(args.pr), title=ev["title"], body=ev["body"],
        head_ref=head, diff_text=ev["diff"], checks_text=ev["checks_text"],
    )
    agent_out = run_agent(
        r, cfg, worktree=review_worktree(cfg, args.repo), prompt=prompt, execute=execute and live,
    )
    if agent_out.get("status") == "planned":
        return emit_exit(ok(offline=not live, planned=True, repo=args.repo, pr=args.pr,
                            branch=head, head_sha=head_sha, merge_ok=False, agent=agent_out))
    if agent_out.get("status") == "failed":
        return emit_exit(err("pr_review agent failed", repo=args.repo, pr=args.pr,
                             merge_ok=False, agent=agent_out))

    stdout = str(agent_out.get("stdout_tail") or "")
    mutate = mutations_allowed(live_flag=args.live, cfg=cfg)
    try:
        decision = coerce_soft_nits(parse_review_output(stdout))
    except PrReviewError as exc:
        applied = publish_fail_closed(r, args.repo, int(args.pr), exc, mutate=mutate)
        return emit_exit(ok(offline=False, skipped=True, reason="invalid_review_json",
                            error=str(exc), repo=args.repo, pr=args.pr, merge_ok=False,
                            applied=applied, agent_stdout_tail=stdout[-2000:]))

    merge_ok, escalated = decide_review_merge(decision, prior_rc, max_request_changes=max_rc)
    try:
        publish_decision(
            r, args.repo, int(args.pr), decision, head_sha=head_sha,
            merge_ok=merge_ok, escalated=escalated, mutate=mutate,
        )
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(f"failed to publish review comment: {exc}",
                             decision=decision.to_dict(), merge_ok=merge_ok, escalated=escalated))
    return emit_exit(ok(
        offline=False, repo=args.repo, pr=args.pr, branch=head, head_sha=head_sha,
        decision=decision.to_dict(), merge_ok=merge_ok, escalated=escalated, applied=mutate,
        request_changes_count=prior_rc + (1 if decision.verdict == "request_changes" else 0),
        agent_status=agent_out.get("status"),
    ))


if __name__ == "__main__":
    raise SystemExit(main())
