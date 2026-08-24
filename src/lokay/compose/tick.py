"""Compatibility CLI: invoke the authored parent factory-pass Fala."""

from __future__ import annotations
import argparse
from typing import Any
from lokay.envelope import emit_exit
from lokay.proc._common import add_config_live


def compose_tick(*, config_path: str | None, live: bool) -> dict[str, Any]:
    from lokay.compose.factory import compose_factory_pass

    return compose_factory_pass(config_path=config_path, live=live)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-tick")
    add_config_live(parser)
    args = parser.parse_args(argv)
    return emit_exit(compose_tick(config_path=args.config, live=bool(args.live)))


if __name__ == "__main__":
    raise SystemExit(main())
