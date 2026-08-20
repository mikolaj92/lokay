"""Atomic: git push -u origin <branch> (never force)."""

from __future__ import annotations

import argparse
from pathlib import Path

from lokay.envelope import emit_exit, err, ok
from lokay.git_push import is_configured_issue_branch, push_branch
from lokay.proc._common import add_config, load_cfg, mutations_allowed, runner
from lokay.mill_scope import SKIP_REASON, mill_repo


MINI_MILL_REPO = mill_repo()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-push")
    add_config(p)
    p.add_argument("--live", action="store_true")
    p.add_argument("--repo", required=True)
    p.add_argument("--worktree", required=True)
    p.add_argument("--branch", required=True)
    args = p.parse_args(argv)
    if args.repo != MINI_MILL_REPO:
        return emit_exit(
            ok(
                planned=not args.live,
                skipped=True,
                reason=SKIP_REASON,
                repo=args.repo,
                branch=args.branch,
                worktree=args.worktree,
            )
        )
    cfg = load_cfg(args) if args.live else None
    run = runner()
    try:
        live = mutations_allowed(live_flag=args.live, cfg=cfg)
    except RuntimeError as exc:
        # A completed issue branch can outlive the mill lease that launched it.
        # Allow only the exact branch in a verified linked issue worktree;
        # configured host checkouts (especially main) remain protected.
        checkouts = tuple(repo.clone_path for repo in getattr(cfg, "repos", ()))
        if "lease=token_mismatch)" not in str(exc) or not is_configured_issue_branch(
            run, Path(args.worktree), args.branch, checkouts
        ):
            return emit_exit(err(str(exc)))
        live = True
    try:
        push_branch(run, Path(args.worktree), args.branch, live=live)
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    return emit_exit(
        ok(
            planned=not live,
            repo=args.repo,
            branch=args.branch,
            worktree=args.worktree,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
