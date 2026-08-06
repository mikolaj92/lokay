"""Atomic: close a PR (e.g. merge conflicts). Mutates only with --live."""

from __future__ import annotations

import argparse

from lokay.envelope import emit_exit, err, ok
from lokay.gh_prs import close_pr
from lokay.proc._common import add_config_live, load_cfg, mutations_allowed, runner


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-pr-close")
    add_config_live(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--pr", required=True, type=int)
    p.add_argument(
        "--comment",
        default="",
        help="optional comment explaining why the PR is closed",
    )
    args = p.parse_args(argv)
    cfg = load_cfg(args)
    live = mutations_allowed(live_flag=args.live)
    try:
        close_pr(
            runner(),
            args.repo,
            int(args.pr),
            live=live,
            comment=str(args.comment or ""),
        )
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    return emit_exit(
        ok(
            planned=not live,
            repo=args.repo,
            pr=int(args.pr),
            closed=live,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
