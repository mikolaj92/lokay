"""Atomic: git add -A && commit if staged diff."""

from __future__ import annotations

import argparse
from pathlib import Path

from lokay.envelope import emit_exit, err, ok
from lokay.git_commit import commit_all
from lokay.proc._common import runner


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-commit-all")
    p.add_argument("--live", action="store_true")
    p.add_argument("--worktree", required=True)
    p.add_argument("--message", required=True)
    args = p.parse_args(argv)
    live = bool(args.live)
    try:
        did = commit_all(runner(), Path(args.worktree), args.message, live=live)
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    return emit_exit(ok(planned=not live, committed=did, worktree=args.worktree))


if __name__ == "__main__":
    raise SystemExit(main())
