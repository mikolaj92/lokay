"""Thin bridge atom: in-process factory-pass spine (not in parent Fala graph).

Parent ``factory_pass`` conducts survey/plan/dispatch atoms directly. This CLI
remains for ``lokay-factory-tick`` and any caller that wants one process that
runs the same spine without hosting Fala.
"""

from __future__ import annotations

import argparse

from lokay.compose.tick import compose_tick
from lokay.envelope import emit_exit
from lokay.proc._common import add_config_live


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-factory-tick")
    add_config_live(parser)
    args = parser.parse_args(argv)
    return emit_exit(compose_tick(config_path=args.config, live=bool(args.live)))


if __name__ == "__main__":
    raise SystemExit(main())
