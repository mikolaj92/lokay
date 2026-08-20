"""Atomic pure: branch name from repo + issue + title."""

from __future__ import annotations

import argparse

from lokay.envelope import emit_exit, ok
from lokay.git_branch import branch_for_issue
from lokay.mill_scope import SKIP_REASON, mill_repo


MINI_MILL_REPO = mill_repo()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-make-branch")
    p.add_argument("--prefix", default="ai/fix")
    p.add_argument("--repo", required=True)
    p.add_argument("--issue", required=True, type=int)
    p.add_argument("--title", default="")
    args = p.parse_args(argv)
    if args.repo != MINI_MILL_REPO:
        return emit_exit(
            ok(
                skipped=True,
                reason=SKIP_REASON,
                repo=args.repo,
                issue=args.issue,
            )
        )
    branch = branch_for_issue(args.prefix, args.repo, args.issue, args.title)
    return emit_exit(ok(branch=branch, repo=args.repo, issue=args.issue))


if __name__ == "__main__":
    raise SystemExit(main())
