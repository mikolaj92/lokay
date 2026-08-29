"""Atomic: ensure git worktree for branch."""

from __future__ import annotations

import argparse

from lokay.code import load_code, slot_from_repo
from lokay.code.github import InvalidBranchRef
from lokay.envelope import emit_exit, err, ok
from lokay.proc._common import add_config_live, load_cfg, mutations_allowed, runner


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
    repo = next((r for r in cfg.repos if r.name == args.repo), None)
    if repo is None:
        return emit_exit(err(f"repo not in config: {args.repo}"))
    live = mutations_allowed(live_flag=args.live, cfg=cfg)
    try:
        contract = load_code(slot_from_repo(repo), runner=runner(), config=cfg, live=live)
        path = contract.repo.worktree(
            args.branch, base=args.base, reset_to_base=bool(args.reset_base)
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
