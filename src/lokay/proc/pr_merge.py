"""Atomic: merge PR (no force/admin)."""

from __future__ import annotations

import argparse

from lokay.envelope import emit_exit, err, ok
from lokay.gh_prs import merge_pr
from lokay.proc._common import add_config_live, load_cfg, mutations_allowed, runner


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-pr-merge")
    add_config_live(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--pr", required=True, type=int)
    args = p.parse_args(argv)
    cfg = load_cfg(args)
    live = mutations_allowed(live_flag=args.live, cfg=cfg)
    if live and not cfg.merge_enabled:
        return emit_exit(err("merge.enabled is false in config", planned=True))
    try:
        merge_pr(runner(), args.repo, args.pr, live=live)
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    return emit_exit(ok(planned=not live, repo=args.repo, pr=args.pr, merged=live))


if __name__ == "__main__":
    raise SystemExit(main())
