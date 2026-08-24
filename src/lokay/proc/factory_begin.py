"""Thin CLI facade for authored factory-pass workspace opening."""

from __future__ import annotations
import argparse
from typing import Any
from lokay.envelope import emit_exit
from lokay.proc._common import add_config_live


def run_factory_begin(*, config_path: str | None, live: bool) -> dict[str, Any]:
    from lokay.proc.factory_begin_subflow import run

    return run(config_path=config_path, live=live)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-factory-begin")
    add_config_live(parser)
    args = parser.parse_args(argv)
    return emit_exit(run_factory_begin(config_path=args.config, live=bool(args.live)))


if __name__ == "__main__":
    raise SystemExit(main())
