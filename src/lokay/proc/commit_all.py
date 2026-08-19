"""Atomic: commit localized changes (or all changes without localization)."""

from __future__ import annotations

import argparse
from pathlib import Path

from lokay.envelope import emit_exit, err, ok
from lokay.git_commit import commit_all, is_configured_issue_worktree
from lokay.proc._common import add_config, load_cfg, mutations_allowed, runner
from lokay.runner import git_spec


MINI_MILL_REPO = "mikolaj92/lokay"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-commit-all")
    add_config(p)
    p.add_argument("--live", action="store_true")
    p.add_argument("--repo", default=MINI_MILL_REPO)
    p.add_argument("--worktree", required=True)
    p.add_argument("--message", required=True)
    args = p.parse_args(argv)
    if args.repo != MINI_MILL_REPO:
        return emit_exit(
            ok(
                planned=not args.live,
                committed=False,
                skipped=True,
                reason="repo_not_delivered_by_mini_mill",
                repo=args.repo,
                worktree=args.worktree,
            )
        )
    cfg = load_cfg(args) if args.live else None
    run = runner()
    try:
        live = mutations_allowed(live_flag=args.live, cfg=cfg)
    except RuntimeError as exc:
        # A coding run can outlive the mill lease that launched it. Preserve
        # completed source only in a verified linked issue worktree; configured
        # host checkouts (especially main) remain protected.
        checkouts = tuple(repo.clone_path for repo in getattr(cfg, "repos", ()))
        if "lease=token_mismatch)" not in str(exc) or not is_configured_issue_worktree(
            run, Path(args.worktree), checkouts
        ):
            return emit_exit(err(str(exc)))
        live = True
    try:
        did = commit_all(
            run,
            Path(args.worktree),
            args.message,
            live=live,
            protected_checkouts=(
                repo.clone_path for repo in getattr(cfg, "repos", ())
            ) if cfg else (),
        )
        commit = ""
        if did:
            commit = run.run_checked(
                git_spec(["rev-parse", "HEAD"], cwd=Path(args.worktree)),
                live=True,
            ).stdout.strip()
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    return emit_exit(
        ok(
            planned=not live,
            committed=did,
            commit=commit,
            repo=args.repo,
            worktree=args.worktree,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
