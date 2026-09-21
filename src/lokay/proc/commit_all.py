"""Atomic: commit localized changes (or all changes without localization)."""

from __future__ import annotations

import argparse
from pathlib import Path

from lokay.envelope import emit_exit, err, ok
from lokay.git_commit import commit_all, is_configured_issue_worktree
from lokay.proc._common import add_config, load_cfg, mutations_allowed, runner
from lokay.proc.repair_agent_revision import observe
from lokay.runner import git_spec


MINI_LOKAY_REPO_SCOPE = "mikolaj92/lokay"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-commit-all")
    add_config(p)
    p.add_argument("--live", action="store_true")
    p.add_argument("--repo", default=MINI_LOKAY_REPO_SCOPE)
    p.add_argument("--worktree", required=True)
    p.add_argument("--message", required=True)
    p.add_argument("--record-repair-revision", action="store_true")
    args = p.parse_args(argv)
    cfg = load_cfg(args) if args.live else None
    run = runner()
    try:
        live = mutations_allowed(live_flag=args.live, cfg=cfg)
    except RuntimeError as exc:
        # A coding run can outlive the lokay lease that launched it. Preserve
        # completed source only in a verified linked issue worktree; configured
        # host checkouts (especially main) remain protected.
        checkouts = tuple(repo.clone_path for repo in getattr(cfg, "repos", ()))
        if "lease=token_mismatch)" not in str(exc) or not is_configured_issue_worktree(
            run, Path(args.worktree), checkouts
        ):
            return emit_exit(err(str(exc)))
        live = True
    revision = {}
    try:
        if live and args.record_repair_revision:
            revision['before'] = observe(run, Path(args.worktree))
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
        if live and args.record_repair_revision:
            revision['after'] = observe(run, Path(args.worktree))
            if did:
                revision['parents'] = run.run_checked(
                    git_spec(['show', '-s', '--format=%P', commit], cwd=Path(args.worktree)),
                    live=True,
                ).stdout.strip().split()
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    return emit_exit(
        ok(
            planned=not live,
            committed=did,
            commit=commit,
            repo=args.repo,
            worktree=args.worktree,
            **({'revision': revision} if revision else {}),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
