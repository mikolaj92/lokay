"""Thin alias: parent Fala ``factory_pass`` (same mill as ``lokay-factory-pass``).

Production always hosts Fala via ``compose_factory_pass`` → ``graph_run.run_path``.
The in-process ``compose_tick`` spine remains for hermetic unit tests only.
"""

from __future__ import annotations

import argparse

from lokay.compose.factory import compose_factory_pass
from lokay.envelope import emit_exit
from lokay.proc._common import add_config_live


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-factory-tick")
    add_config_live(parser)
    parser.add_argument("--db-dir", help="parent Fala journal directory")
    args = parser.parse_args(argv)
    return emit_exit(
        compose_factory_pass(
            config_path=args.config,
            live=bool(args.live),
            db_path=args.db_dir,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
