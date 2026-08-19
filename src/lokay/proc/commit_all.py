"""Atomic: commit localized changes (or all changes without localization)."""

from __future__ import annotations

import argparse
from pathlib import Path

from lokay.envelope import emit_exit, err, ok
from lokay.git_commit import commit_all
from lokay.proc._common import add_config, load_cfg, mutations_allowed, runner
from lokay.runner import git_spec


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-commit-all")
    add_config(p)
    p.add_argument("--live", action="store_true")
    p.add_argument("--worktree", required=True)
    p.add_argument("--message", required=True)
    args = p.parse_args(argv)
    cfg = load_cfg(args) if args.live else None
    live = mutations_allowed(live_flag=args.live, cfg=cfg)
    run = runner()
    try:
        did = commit_all(run, Path(args.worktree), args.message, live=live)
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
            worktree=args.worktree,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
