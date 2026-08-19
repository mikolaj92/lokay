"""Atomic: rebase the issue_to_pr corner onto origin/<base> or fail closed."""

from __future__ import annotations

import argparse
from pathlib import Path

from lokay.envelope import emit_exit, err, ok
from lokay.git_rebase import RebaseConflict, RebaseError, rebase_onto_base
from lokay.proc._common import add_config, load_cfg, mutations_allowed, runner


MINI_MILL_REPO = "mikolaj92/lokay"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-rebase-onto-base")
    add_config(parser)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--worktree", required=True)
    parser.add_argument("--base", default="main")
    args = parser.parse_args(argv)
    if args.repo != MINI_MILL_REPO:
        return emit_exit(
            ok(
                planned=not args.live,
                skipped=True,
                reason="repo_not_delivered_by_mini_mill",
                repo=args.repo,
                worktree=args.worktree,
            )
        )
    cfg = load_cfg(args) if args.live else None
    live = mutations_allowed(live_flag=args.live, cfg=cfg)
    try:
        receipt = rebase_onto_base(
            runner(),
            Path(args.worktree),
            live=live,
            base=str(args.base or "main"),
        )
    except RebaseConflict as exc:
        return emit_exit(err(str(exc), reason=exc.reason, worktree=args.worktree))
    except RebaseError as exc:
        return emit_exit(err(str(exc), reason=exc.reason, worktree=args.worktree))
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc), reason="rebase_failed", worktree=args.worktree))
    return emit_exit(ok(repo=args.repo, worktree=args.worktree, **receipt))


if __name__ == "__main__":
    raise SystemExit(main())
