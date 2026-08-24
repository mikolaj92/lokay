"""Thin CLI facade for authored physical real-diff assertion."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

_SCOPED_ROOTS = {"fala", "src", "tests"}


def _paths_outside_scope(changed: list[str], scope: list[str]) -> list[str]:
    def allowed(path: str) -> bool:
        return any(path == item or path.startswith(f"{item}/") for item in scope)

    normalized = [path.removeprefix("./") for path in changed]
    return [
        path
        for path in normalized
        if path.split("/", 1)[0] in _SCOPED_ROOTS and not allowed(path)
    ]


def _off_goal_paths(changed: list[str], localized: list[str]) -> list[str]:
    return _paths_outside_scope(changed, localized)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-assert-real-diff")
    parser.add_argument("--worktree", required=True)
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--issue-body", default="")
    args = parser.parse_args(argv)
    from lokay.proc.assert_real_diff_subflow import run

    result = run(
        worktree=str(Path(args.worktree).resolve()),
        base=args.base,
        issue_body=args.issue_body,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
