"""Atomic subprocess boundary: execute one bounded product mill."""

from __future__ import annotations

import argparse

from lokay.compose.mill import compose_mill
from lokay.envelope import emit_exit
from lokay.proc._common import add_config_live


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-recovery-mill")
    add_config_live(parser)
    parser.add_argument("--max-passes", type=int, default=8)
    args = parser.parse_args(argv)
    # Domain failure is data for downstream recovery observation. The Fala
    # effector itself succeeds so conduction can always classify this run.
    mill = compose_mill(
        config_path=args.config,
        live=bool(args.live),
        max_passes=max(1, args.max_passes),
    )
    return emit_exit({"ok": True, "mill": mill})


if __name__ == "__main__":
    raise SystemExit(main())
