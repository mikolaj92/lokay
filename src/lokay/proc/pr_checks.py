"""Atomic: gh pr checks. Read-only; network by default."""

from __future__ import annotations

import argparse

from lokay.envelope import emit_exit, err, ok
from lokay.gh_prs import pr_checks_green
from lokay.proc._common import add_config_read, load_cfg, read_live, runner


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-pr-checks")
    add_config_read(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--pr", required=True, type=int)
    args = p.parse_args(argv)
    cfg = load_cfg(args)
    live = read_live(args)
    try:
        green, text = pr_checks_green(runner(), args.repo, args.pr, live=live)
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    return emit_exit(
        ok(
            offline=not live,
            repo=args.repo,
            pr=args.pr,
            green=green,
            text=text[-4000:],
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
