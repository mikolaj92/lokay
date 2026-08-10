"""Atomic: close a GitHub issue. Mutates only with --live."""

from __future__ import annotations

import argparse

from lokay.envelope import emit_exit, err, ok
from lokay.gh_issues import close_issue, comment_issue
from lokay.proc._common import add_config_live, load_cfg, mutations_allowed, runner


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-close-issue")
    add_config_live(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--issue", required=True, type=int)
    p.add_argument("--comment", default="", help="optional closing comment")
    args = p.parse_args(argv)
    cfg = load_cfg(args)
    live = mutations_allowed(live_flag=args.live, cfg=cfg)
    try:
        if args.comment:
            comment_issue(runner(), args.repo, args.issue, args.comment, live=live)
        close_issue(runner(), args.repo, args.issue, live=live)
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    return emit_exit(
        ok(
            planned=not live,
            repo=args.repo,
            issue=args.issue,
            closed=live,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
