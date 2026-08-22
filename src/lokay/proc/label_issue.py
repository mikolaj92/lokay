"""Atomic: add or remove label(s) on a GitHub issue. Mutates only with --live."""

from __future__ import annotations

import argparse

from lokay.envelope import emit_exit, err, ok
from lokay.gh_issues import add_issue_labels, remove_issue_labels
from lokay.proc._common import add_config_live, load_cfg, mutations_allowed, runner




def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-label-issue")
    add_config_live(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--issue", required=True, type=int)
    p.add_argument(
        "--label",
        action="append",
        dest="labels",
        required=True,
        help="label to add/remove (repeatable)",
    )
    p.add_argument(
        "--remove",
        action="store_true",
        help="remove labels instead of adding",
    )
    args = p.parse_args(argv)
    labels = [str(x) for x in (args.labels or []) if x]
    if not labels:
        return emit_exit(err("at least one --label required"))
    cfg = load_cfg(args)
    live = mutations_allowed(live_flag=args.live, cfg=cfg)
    try:
        if args.remove:
            remove_issue_labels(runner(), args.repo, args.issue, labels, live=live)
        else:
            add_issue_labels(runner(), args.repo, args.issue, labels, live=live)
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    return emit_exit(
        ok(
            planned=not live,
            repo=args.repo,
            issue=args.issue,
            labels=labels,
            removed=bool(args.remove),
            applied=live,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
