"""Atomic: publish one validated recovery commit to main, fast-forward only."""

from __future__ import annotations

import argparse
from pathlib import Path

from lokay.envelope import emit_exit, err, ok
from lokay.proc._common import add_config_live, load_cfg, mutations_allowed, runner
from lokay.runner import git_spec


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-self-repair-push-main")
    add_config_live(p)
    p.add_argument("--worktree", required=True)
    p.add_argument("--base-sha", required=True)
    p.add_argument("--validated", action="store_true", required=True)
    p.add_argument("--expected-commit", default="")
    args = p.parse_args(argv)
    cfg = load_cfg(args)
    live = mutations_allowed(live_flag=args.live, cfg=cfg)
    worktree = Path(args.worktree).resolve()
    if not live:
        return emit_exit(ok(planned=True, branch="main", worktree=str(worktree)))
    run = runner()
    try:
        run.run_checked(
            git_spec(["fetch", "origin", "main"], cwd=worktree, timeout_seconds=300),
            live=True,
        )
        remote = run.run_checked(
            git_spec(["rev-parse", "origin/main"], cwd=worktree), live=True
        ).stdout.strip()
        if remote != args.base_sha:
            raise RuntimeError("origin/main changed during self-repair")
        head = run.run_checked(
            git_spec(["rev-parse", "HEAD"], cwd=worktree), live=True
        ).stdout.strip()
        if head == args.base_sha:
            raise RuntimeError("self-repair produced no commit")
        if args.expected_commit and head != args.expected_commit:
            raise RuntimeError("self-repair candidate changed after validation")
        run.run_checked(
            git_spec(
                ["push", "origin", f"{head}:refs/heads/main"],
                cwd=worktree,
                timeout_seconds=300,
            ),
            live=True,
        )
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    return emit_exit(ok(planned=False, pushed=True, branch="main", base_sha=args.base_sha, commit=head))


if __name__ == "__main__":
    raise SystemExit(main())
