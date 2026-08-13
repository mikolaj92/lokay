"""One job: refuse a worktree whose diff is only plan/localize evidence.

A commit/PR that only ships ``.lokay/approach.md`` / ``.lokay/localize.json``
(and trivial lockstep of those) is not progress. Callers must not ``pr_create``.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from lokay.envelope import emit_exit, err, ok
from lokay.git_real_diff import classify_changed_paths, list_changed_paths
from lokay.proc._common import runner


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-assert-real-diff")
    parser.add_argument("--worktree", required=True)
    parser.add_argument("--base", default="origin/main")
    args = parser.parse_args(argv)
    worktree = Path(args.worktree).resolve()
    if not worktree.is_dir():
        return emit_exit(err("worktree is not a directory", worktree=str(worktree)))
    try:
        paths = list_changed_paths(runner(), worktree, base=str(args.base))
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc), worktree=str(worktree)))
    kind = classify_changed_paths(paths)
    if kind == "real":
        return emit_exit(
            ok(
                real=True,
                kind=kind,
                paths=paths,
                worktree=str(worktree),
                base=str(args.base),
            )
        )
    reason = "plan_only" if kind == "plan_only" else "zero_diff"
    message = (
        "refusing: diff is only plan/localize evidence "
        "(.lokay/approach.md / .lokay/localize.json); not progress"
        if kind == "plan_only"
        else "refusing: empty diff vs base; not progress"
    )
    return emit_exit(
        err(
            message,
            reason=reason,
            kind=kind,
            real=False,
            paths=paths,
            worktree=str(worktree),
            base=str(args.base),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
