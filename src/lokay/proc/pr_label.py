"""Atomic: add labels to a PR."""

from __future__ import annotations

import argparse

from lokay.envelope import emit_exit, err, ok
from lokay.gh_prs import add_pr_labels
from lokay.proc._common import add_config_live, load_cfg, mutations_allowed, runner


MINI_MILL_REPO = "mikolaj92/lokay"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-pr-label")
    add_config_live(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--pr", required=True, type=int)
    p.add_argument("--label", action="append", dest="labels", default=[])
    args = p.parse_args(argv)
    if args.repo != MINI_MILL_REPO:
        return emit_exit(
            ok(
                planned=not args.live,
                skipped=True,
                reason="repo_not_delivered_by_mini_mill",
                repo=args.repo,
                pr=args.pr,
                labels=args.labels,
                applied=False,
            )
        )
    cfg = load_cfg(args)
    live = mutations_allowed(live_flag=args.live, cfg=cfg)
    labels = args.labels or list(cfg.pr_labels)
    try:
        add_pr_labels(runner(), args.repo, args.pr, labels, live=live)
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    return emit_exit(
        ok(
            planned=not live,
            applied=bool(live and labels),
            repo=args.repo,
            pr=args.pr,
            labels=labels,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
