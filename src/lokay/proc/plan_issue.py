"""Thin CLI facade for authored deterministic issue planning."""

import argparse
import json
from pathlib import Path

from lokay.approach_plan import APPROACH_REL_PATH
from lokay.envelope import emit_exit, err
from lokay.proc._common import add_config_live


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-plan-issue")
    add_config_live(p)
    p.add_argument("--worktree", required=True)
    p.add_argument("--repo", default="")
    p.add_argument("--issue", type=int)
    p.add_argument("--title", default="")
    p.add_argument("--body", default="")
    p.add_argument("--url", default="")
    p.add_argument("--issue-json", default="")
    p.add_argument("--rel-path", default=APPROACH_REL_PATH)
    p.add_argument("--llm", action="store_true")
    args = p.parse_args(argv)
    if args.llm:
        return emit_exit(
            err(
                "plan_issue is deterministic; semantic agents belong to authored decision subflows",
                llm_requested=True,
            )
        )
    try:
        raw = (
            json.loads(Path(args.issue_json).read_text(encoding="utf-8"))
            if args.issue_json
            else {}
        )
        from lokay.proc.plan_issue_subflow import run

        out = run(
            config_path=args.config,
            live=bool(args.live),
            worktree=args.worktree,
            issue_raw=raw,
            repo=args.repo,
            issue=args.issue,
            title=args.title,
            body=args.body,
            url=args.url,
            rel_path=args.rel_path,
        )
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    return emit_exit(out)


if __name__ == "__main__":
    raise SystemExit(main())
