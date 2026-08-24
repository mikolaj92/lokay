"""Thin CLI facade for authored one-retry off-goal relocalization."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lokay.envelope import emit_exit, err


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-relocalize-off-goal")
    p.add_argument("--config")
    p.add_argument("--live", action="store_true")
    p.add_argument("--worktree", required=True)
    p.add_argument("--base", default="origin/main")
    p.add_argument("--issue-json", default="")
    args = p.parse_args(argv)
    try:
        issue = (
            json.loads(Path(args.issue_json).read_text(encoding="utf-8"))
            if args.issue_json
            else {}
        )
        from lokay.proc.relocalize_off_goal_subflow import run

        out = run(
            config_path=args.config,
            live=bool(args.live),
            extra_inputs={
                "worktree": args.worktree,
                "base": args.base,
                "repo": str(issue.get("repo") or ""),
                "issue_raw": issue,
            },
        )
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    return emit_exit(out)


if __name__ == "__main__":
    raise SystemExit(main())
