"""Atomic: assign configured maintainer on an issue."""

from __future__ import annotations

import argparse

from lokay.envelope import emit_exit, err, ok
from lokay.gh_issues import assign_issue
from lokay.proc._common import add_config_live, load_cfg, mutations_allowed, runner


MINI_MILL_REPO = "mikolaj92/lokay"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-assign-issue")
    add_config_live(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--issue", required=True, type=int)
    args = p.parse_args(argv)
    if args.repo != MINI_MILL_REPO:
        return emit_exit(
            ok(
                planned=not args.live,
                skipped=True,
                reason="repo_not_delivered_by_mini_mill",
                repo=args.repo,
                issue=args.issue,
                applied=False,
            )
        )
    cfg = load_cfg(args)
    live = mutations_allowed(live_flag=args.live, cfg=cfg)
    try:
        assign_issue(runner(), cfg, args.repo, args.issue, live=live)
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    return emit_exit(
        ok(
            planned=not live,
            applied=live,
            repo=args.repo,
            issue=args.issue,
            assignee=cfg.assignee,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
