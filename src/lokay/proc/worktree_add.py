"""Atomic: ensure git worktree for branch.

Always succeeds. Fala unblocks children of a failed atom, so `ok=false`
cannot stop plan/localize/coding. `route=ready` continues; `route=missing`
means no local clone or the worktree could not be created.
"""

from __future__ import annotations

import argparse

from lokay.code.github import InvalidBranchRef
from lokay.envelope import emit_exit, ok
from lokay.proc._common import add_config_live, load_cfg, mutations_allowed, runner
from lokay.source import load_code


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
        return emit_exit(
            ok(
                route="missing",
                reason="repo_not_in_config",
                error=f"repo not in config: {args.repo}",
                repo=args.repo,
                branch=args.branch,
            )
        )
    if not repo.clone_path.exists():
        return emit_exit(
            ok(
                route="missing",
                reason="clone_path_missing",
                repo=args.repo,
                branch=args.branch,
                clone_path=str(repo.clone_path),
                planned=not mutations_allowed(live_flag=args.live, cfg=cfg),
            )
        )
    live = mutations_allowed(live_flag=args.live, cfg=cfg)
    try:
        contract = load_code(repo, runner=runner(), config=cfg, live=live)
        path = contract.repo.worktree(
            args.branch, base=args.base, reset_to_base=bool(args.reset_base)
        )
    except InvalidBranchRef as exc:
        return emit_exit(
            ok(
                route="missing",
                reason=exc.reason,
                error=str(exc),
                repo=args.repo,
                branch=args.branch,
                clone_path=str(repo.clone_path),
            )
        )
    except Exception as exc:  # noqa: BLE001
        return emit_exit(
            ok(
                route="missing",
                reason="worktree_failed",
                error=str(exc),
                repo=args.repo,
                branch=args.branch,
                clone_path=str(repo.clone_path),
            )
        )
    return emit_exit(
        ok(
            route="ready",
            planned=not live,
            repo=args.repo,
            branch=args.branch,
            worktree=str(path),
            reset_to_base=bool(args.reset_base),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
