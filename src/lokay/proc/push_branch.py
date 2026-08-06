"""Atomic: git push -u origin <branch> (never force)."""

from __future__ import annotations

import argparse
from pathlib import Path

from lokay.envelope import emit_exit, err, ok
from lokay.git_push import push_branch
from lokay.proc._common import runner


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-push")
    p.add_argument("--live", action="store_true")
    p.add_argument("--worktree", required=True)
    p.add_argument("--branch", required=True)
    args = p.parse_args(argv)
    live = bool(args.live)
    try:
        push_branch(runner(), Path(args.worktree), args.branch, live=live)
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    return emit_exit(ok(planned=not live, branch=args.branch, worktree=args.worktree))


if __name__ == "__main__":
    raise SystemExit(main())
