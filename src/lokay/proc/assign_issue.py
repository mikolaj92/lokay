"""Atomic: assign configured maintainer on an issue."""

from __future__ import annotations

import argparse

from lokay.envelope import emit_exit, err, ok
from lokay.gh_issues import assign_issue, get_issue
from lokay.proc._common import add_config_live, load_cfg, mutations_allowed, runner
from lokay.proc.classify_issue_assignee import takeable



def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-assign-issue")
    add_config_live(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--issue", required=True, type=int)
    args = p.parse_args(argv)
    cfg = load_cfg(args)
    live = mutations_allowed(live_flag=args.live, cfg=cfg)
    git = runner()
    current: list[str] | None = None
    if live:
        issue = get_issue(git, cfg, args.repo, args.issue, live=True)
        current = list(issue.assignees) if issue else []
        if not takeable({"assignees": current}, cfg.assignee):
            return emit_exit(
                err(
                    "foreign_assignee",
                    repo=args.repo,
                    issue=args.issue,
                    assignee=cfg.assignee,
                    assignees=current,
                    applied=False,
                )
            )
    try:
        assign_issue(git, cfg, args.repo, args.issue, live=live)
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    return emit_exit(
        ok(
            planned=not live,
            applied=live,
            repo=args.repo,
            issue=args.issue,
            assignee=cfg.assignee,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
