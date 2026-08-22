"""Atomic: merge PR (no force/admin)."""

from __future__ import annotations

import argparse

from lokay.envelope import emit_exit, err, ok
from lokay.gh_prs import merge_pr
from lokay.passkit.support import run_proc
from lokay.proc import unbounded_park
from lokay.proc._common import add_config_live, load_cfg, mutations_allowed, runner
from lokay.mill_scope import SKIP_REASON, mill_repo

MINI_MILL_REPO = mill_repo()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-pr-merge")
    add_config_live(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--pr", required=True, type=int)
    p.add_argument("--issue", type=int)
    args = p.parse_args(argv)
    if args.repo != MINI_MILL_REPO:
        return emit_exit(
            ok(
                planned=False,
                skipped=True,
                reason=SKIP_REASON,
                repo=args.repo,
                pr=args.pr,
                merged=False,
                issue=args.issue,
                parked=None,
            )
        )
    cfg = load_cfg(args)
    live = mutations_allowed(live_flag=args.live, cfg=cfg)
    if live and not cfg.merge_enabled:
        return emit_exit(err("merge.enabled is false in config", planned=True))
    try:
        merge_pr(runner(), args.repo, args.pr, live=live)
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    parked = None
    if live and args.issue is not None:
        parked = run_proc(
            unbounded_park.main,
            [
                *(["--config", args.config] if args.config else []),
                "--live",
                "--repo",
                args.repo,
                "--issue",
                str(args.issue),
            ],
        )
    return emit_exit(
        ok(
            planned=not live,
            repo=args.repo,
            pr=args.pr,
            merged=live,
            issue=args.issue,
            parked=parked,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
