"""Atomic: ensure git worktree for branch."""

from __future__ import annotations

import argparse

from lokay.envelope import emit_exit, err, ok
from lokay.git_worktree import InvalidBranchRef, ensure_worktree
from lokay.proc._common import add_config_live, load_cfg, mutations_allowed, runner


MINI_MILL_REPO = "mikolaj92/lokay"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-worktree-add")
    add_config_live(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--branch", required=True)
    p.add_argument("--base", default="main")
    p.add_argument(
        "--reset-base",
        action="store_true",
        help="recreate branch/worktree from origin/<base> (issue_to_pr re-implement)",
    )
    args = p.parse_args(argv)
    cfg = load_cfg(args)
    live = mutations_allowed(live_flag=args.live, cfg=cfg)
    repo = next((r for r in cfg.repos if r.name == args.repo), None)
    if repo is None:
        return emit_exit(err(f"repo not in config: {args.repo}"))
    if repo.name != MINI_MILL_REPO:
        return emit_exit(
            ok(
                planned=not live,
                skipped=True,
                reason="repo_not_delivered_by_mini_mill",
                repo=args.repo,
                branch=args.branch,
            )
        )
    try:
        path = ensure_worktree(
            runner(),
            cfg,
            repo,
            args.branch,
            live=live,
            base=args.base,
            reset_to_base=bool(args.reset_base),
        )
    except InvalidBranchRef as exc:
        return emit_exit(err(str(exc), reason=exc.reason))
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    return emit_exit(
        ok(
            planned=not live,
            repo=args.repo,
            branch=args.branch,
            worktree=str(path),
            reset_to_base=bool(args.reset_base),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
