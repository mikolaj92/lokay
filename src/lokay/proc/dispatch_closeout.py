"""Thin bridge: resolve_conflicts then closeout_prs (legacy CLI / tests).

Parent ``factory_pass`` conducts those atoms as separate Fala nodes. This entry
point keeps ``lokay-dispatch-closeout`` working as one process.
"""

from __future__ import annotations

import argparse
from typing import Any

from lokay.envelope import emit_exit, err, ok
from lokay.proc.closeout_prs import run_closeout_prs
from lokay.proc._common import add_config_live
from lokay.proc.resolve_conflicts import run_resolve_conflicts


def run_dispatch_closeout(*, pass_dir: str, config_path: str | None, live: bool) -> dict[str, Any]:
    conflicts = run_resolve_conflicts(
        pass_dir=pass_dir, config_path=config_path, live=live
    )
    if not conflicts.get("ok"):
        return conflicts
    closeout = run_closeout_prs(
        pass_dir=pass_dir, config_path=config_path, live=live
    )
    if not closeout.get("ok"):
        return closeout
    return ok(
        pass_dir=pass_dir,
        closed=conflicts.get("closed"),
        remaining_prs=closeout.get("remaining_prs"),
        actionable_prs=closeout.get("actionable_prs"),
        needs_repair=closeout.get("needs_repair"),
        mergeable_green=closeout.get("mergeable_green"),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-dispatch-closeout")
    add_config_live(parser)
    parser.add_argument("--pass-dir", required=True)
    args = parser.parse_args(argv)
    if not args.pass_dir:
        return emit_exit(err("pass-dir required"))
    return emit_exit(
        run_dispatch_closeout(
            pass_dir=str(args.pass_dir),
            config_path=args.config,
            live=bool(args.live),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
