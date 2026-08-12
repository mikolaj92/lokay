"""Atomic: LLM structured review of an AI PR (configured executor). Fail closed on bad JSON."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from lokay.agent import run_agent
from lokay.envelope import emit_exit, err, ok
from lokay.gh_issues import ensure_labels
from lokay.gh_prs import add_pr_labels
from lokay.pr_review import (
    PrReviewError,
    build_review_comment_body,
    coerce_soft_nits,
    count_request_changes_reviews,
    find_review_for_head,
    parse_review_markers,
    parse_review_output,
    review_prompt,
    should_escalate_request_changes,
    should_label_needs_review,
    should_merge,
)
from lokay.proc._common import (
    add_config_live,
    agent_execute_allowed,
    load_cfg,
    mutations_allowed,
    resolve_repo_clone,
    runner,
)
from lokay.runner import gh_spec


def _gh_json(runner_, args: list[str], *, live: bool) -> dict:
    result = runner_.run_checked(gh_spec(args, timeout_seconds=120), live=live)
    if not live:
        return {}
    return json.loads(result.stdout or "{}")


def _gh_text(runner_, args: list[str], *, live: bool) -> str:
    result = runner_.run(gh_spec(args, timeout_seconds=120), live=live)
    if not live:
        return ""
    return ((result.stdout or "") + "\n" + (result.stderr or "")).strip()


def _comment_bodies(view: dict) -> list[str]:
    comments = view.get("comments") or []
    if not isinstance(comments, list):
        return []
    bodies: list[str] = []
    for row in comments:
        if isinstance(row, dict) and isinstance(row.get("body"), str):
            bodies.append(row["body"])
        elif isinstance(row, str):
            bodies.append(row)
    return bodies


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-pr-review")
    add_config_live(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--pr", required=True, type=int)
    p.add_argument("--branch", default="")
    p.add_argument(
        "--checks-text",
        default="",
        help="optional CI text; otherwise re-fetched lightly via pr view",
    )
    args = p.parse_args(argv)
    cfg = load_cfg(args)
    live = bool(args.live)
    execute = agent_execute_allowed(cfg, live_flag=args.live)
    r = runner()

    if live and cfg.mode != "live":
        return emit_exit(err("refusing live pr_review while config mode is not live"))

    if not cfg.executor_enabled:
        return emit_exit(
            ok(
                offline=not live,
                skipped=True,
                reason="executor_disabled",
                repo=args.repo,
                pr=args.pr,
                merge_ok=False,
            )
        )

    # Gather evidence (deterministic gh)
    view = _gh_json(
        r,
        [
            "pr",
            "view",
            str(args.pr),
            "--repo",
            args.repo,
            "--json",
            "number,title,body,headRefName,headRefOid,url,isDraft,mergeable,comments",
        ],
        live=live,
    )
    title = str(view.get("title") or "")
    body = str(view.get("body") or "")
    head = str(args.branch or view.get("headRefName") or "")
    head_sha = str(view.get("headRefOid") or "").strip().lower()
    markers = parse_review_markers(_comment_bodies(view))
    prior_for_head = find_review_for_head(markers, head_sha)
    prior_request_changes = count_request_changes_reviews(markers)
    max_rc = max(1, int(getattr(cfg, "max_request_changes_per_pr", 2)))

    # Idempotent: do not re-run the LLM or re-post for the same head SHA.
    if live and head_sha and prior_for_head is not None:
        prior_verdict = str(prior_for_head.get("verdict") or "")
        prior_merge_ok = bool(prior_for_head.get("merge_ok"))
        return emit_exit(
            ok(
                offline=False,
                skipped=True,
                reason="already_reviewed_head",
                repo=args.repo,
                pr=args.pr,
                branch=head,
                head_sha=head_sha,
                decision={"verdict": prior_verdict},
                merge_ok=prior_merge_ok,
                applied=False,
                request_changes_count=prior_request_changes,
            )
        )

    diff = _gh_text(
        r,
        ["pr", "diff", str(args.pr), "--repo", args.repo],
        live=live,
    )
    checks_text = args.checks_text
    if not checks_text and live:
        checks_text = _gh_text(
            r,
            ["pr", "checks", str(args.pr), "--repo", args.repo],
            live=live,
        )

    prompt = review_prompt(
        repo=args.repo,
        pr_number=int(args.pr),
        title=title,
        body=body,
        head_ref=head,
        diff_text=diff,
        checks_text=checks_text,
    )

    # The executor requires a cwd; prefer configured clone, else temp dir (review is read-only)
    try:
        worktree = resolve_repo_clone(cfg, args.repo)
        if not worktree.is_dir():
            raise KeyError(args.repo)
    except Exception:
        worktree = Path(tempfile.mkdtemp(prefix="lokay-pr-review-"))

    agent_out = run_agent(
        r,
        cfg,
        worktree=worktree,
        prompt=prompt,
        execute=execute and live,
    )

    if agent_out.get("status") == "planned":
        return emit_exit(
            ok(
                offline=not live,
                planned=True,
                repo=args.repo,
                pr=args.pr,
                branch=head,
                head_sha=head_sha,
                merge_ok=False,
                agent=agent_out,
            )
        )

    if agent_out.get("status") == "failed":
        return emit_exit(
            err(
                "pr_review agent failed",
                repo=args.repo,
                pr=args.pr,
                merge_ok=False,
                agent=agent_out,
            )
        )

    stdout = str(agent_out.get("stdout_tail") or "")
    try:
        decision = coerce_soft_nits(parse_review_output(stdout))
    except PrReviewError as exc:
        # Fail closed: never approve on parse failure
        comment = (
            f"Lokay LLM PR review failed closed (invalid structured output): {exc}\n"
            "Will not auto-merge until a valid review is produced."
        )
        applied = False
        if mutations_allowed(live_flag=args.live, cfg=cfg):
            try:
                r.run_checked(
                    gh_spec(
                        [
                            "pr",
                            "comment",
                            str(args.pr),
                            "--repo",
                            args.repo,
                            "--body",
                            comment,
                        ],
                        timeout_seconds=60,
                    ),
                    live=True,
                )
                ensure_labels(
                    r,
                    args.repo,
                    ["ai:needs-review"],
                    live=True,
                )
                add_pr_labels(
                    r, args.repo, int(args.pr), ["ai:needs-review"], live=True
                )
                applied = True
            except Exception:
                applied = False
        return emit_exit(
            ok(
                offline=False,
                skipped=True,
                reason="invalid_review_json",
                error=str(exc),
                repo=args.repo,
                pr=args.pr,
                merge_ok=False,
                applied=applied,
                agent_stdout_tail=stdout[-2000:],
            )
        )

    merge_ok = should_merge(decision)
    escalated = False
    if (
        decision.verdict == "request_changes"
        and not decision.secrets
        and should_escalate_request_changes(prior_request_changes, max_request_changes=max_rc)
    ):
        escalated = True
        # Cap reached: fail closed to human review; never auto-merge / auto-repair.
        merge_ok = False

    applied = False
    if mutations_allowed(live_flag=args.live, cfg=cfg):
        try:
            body = build_review_comment_body(
                decision,
                head_sha=head_sha,
                merge_ok=merge_ok and not escalated,
                escalated=escalated,
            )
            r.run_checked(
                gh_spec(
                    [
                        "pr",
                        "comment",
                        str(args.pr),
                        "--repo",
                        args.repo,
                        "--body",
                        body,
                    ],
                    timeout_seconds=60,
                ),
                live=True,
            )
            labels: list[str] = []
            # Fail closed: secrets / needs_human / request_changes cap only.
            # Soft documentation nits never park a PR for humans.
            if should_label_needs_review(decision, escalated=escalated):
                labels.append("ai:needs-review")
            if decision.verdict == "request_changes" and not escalated:
                labels.append("ai:request-changes")
            if labels:
                ensure_labels(r, args.repo, labels, live=True)
                add_pr_labels(r, args.repo, int(args.pr), labels, live=True)
            applied = True
        except Exception as exc:  # noqa: BLE001
            return emit_exit(
                err(
                    f"failed to publish review comment: {exc}",
                    decision=decision.to_dict(),
                    merge_ok=merge_ok,
                    escalated=escalated,
                )
            )

    return emit_exit(
        ok(
            offline=False,
            repo=args.repo,
            pr=args.pr,
            branch=head,
            head_sha=head_sha,
            decision=decision.to_dict(),
            merge_ok=merge_ok and not escalated,
            escalated=escalated,
            applied=applied,
            request_changes_count=prior_request_changes + (
                1 if decision.verdict == "request_changes" else 0
            ),
            agent_status=agent_out.get("status"),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
