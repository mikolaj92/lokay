"""Atomic: gh pr create."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from lokay.envelope import emit_exit, err, ok
from lokay.gh_issues import get_issue
from lokay.gh_prs import create_pr, find_pr_fixing_issue
from lokay.proc._common import add_config_live, load_cfg, mutations_allowed, runner
from lokay.stuck import issue_number_from_branch




def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-pr-create")
    add_config_live(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--issue", type=int)
    p.add_argument("--title", required=True)
    p.add_argument("--body-file", help="PR body file")
    p.add_argument("--body", default="")
    p.add_argument("--head", required=True)
    p.add_argument("--base", default="main")
    args = p.parse_args(argv)
    cfg = load_cfg(args)
    live = mutations_allowed(live_flag=args.live, cfg=cfg)
    # The PR head identifies the issue worktree.  Prefer it over a stale issue
    # input that may have survived from the preceding factory pass.
    head_issue = issue_number_from_branch(
        args.head, branch_prefix=cfg.branch_prefix
    )
    issue_number = head_issue if head_issue is not None else args.issue
    body = args.body
    if args.body_file:
        body = Path(args.body_file).read_text(encoding="utf-8")
    if (
        head_issue is not None
        and args.issue is not None
        and head_issue != args.issue
    ):
        stale_link = re.compile(
            rf"(\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+)#{args.issue}\b",
            re.IGNORECASE,
        )
        body = stale_link.sub(rf"\g<1>#{head_issue}", body)
    if issue_number is not None:
        body = (
            f"{body}\nFixes #{issue_number}"
            if body
            else f"Fixes #{issue_number}"
        )
    try:
        if issue_number is not None:
            existing = find_pr_fixing_issue(
                runner(), args.repo, issue_number, live=live
            )
            if existing is not None:
                return emit_exit(
                    ok(
                        planned=False,
                        existing=True,
                        pr=existing.get("number"),
                        pull=existing,
                        repo=args.repo,
                        head=existing.get("head", {}).get("ref", args.head),
                    )
                )
            issue = get_issue(
                runner(), cfg, args.repo, issue_number, live=live
            )
            if issue is None:
                return emit_exit(
                    err(
                        f"refusing: issue {args.repo}#{issue_number} was not found",
                        reason="issue_closed",
                        issue_state="MISSING",
                        issue=issue_number,
                        repo=args.repo,
                    )
                )
            issue_state = str(issue.state or "").upper()
            if issue_state != "OPEN":
                return emit_exit(
                    err(
                        f"refusing: issue {args.repo}#{issue_number} is {issue_state}",
                        reason="issue_closed",
                        issue_state=issue_state,
                        issue=issue_number,
                        repo=args.repo,
                    )
                )
        pr = create_pr(
            runner(),
            repo=args.repo,
            title=args.title,
            body=body,
            head=args.head,
            base=args.base,
            live=live,
        )
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    number = pr.get("number")
    return emit_exit(
        ok(
            planned=not live,
            pr=number,
            pull=pr,
            repo=args.repo,
            head=args.head,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
