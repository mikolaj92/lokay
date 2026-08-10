"""Atomic: gh pr create."""

from __future__ import annotations

import argparse
from pathlib import Path

from lokay.envelope import emit_exit, err, ok
from lokay.gh_prs import create_pr
from lokay.proc._common import add_config_live, load_cfg, mutations_allowed, runner


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-pr-create")
    add_config_live(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--body-file", help="PR body file")
    p.add_argument("--body", default="")
    p.add_argument("--head", required=True)
    p.add_argument("--base", default="main")
    args = p.parse_args(argv)
    cfg = load_cfg(args)
    live = mutations_allowed(live_flag=args.live, cfg=cfg)
    body = args.body
    if args.body_file:
        body = Path(args.body_file).read_text(encoding="utf-8")
    try:
        pr = create_pr(
            runner(),
            repo=args.repo,
            title=args.title,
            body=body,
            head=args.head,
            base=args.base,
            live=live,
        )
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    return emit_exit(ok(planned=not live, pr=pr))


if __name__ == "__main__":
    raise SystemExit(main())
