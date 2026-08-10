from __future__ import annotations

import argparse

from lokay.envelope import emit_exit
from lokay.preflight import run_preflight
from lokay.proc._common import add_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-preflight")
    add_config(parser)
    parser.add_argument("--no-repair", action="store_true")
    args = parser.parse_args(argv)
    return emit_exit(run_preflight(args.config, remediate=not args.no_repair))


if __name__ == "__main__":
    raise SystemExit(main())
