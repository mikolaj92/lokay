"""Atomic subprocess boundary: execute one parent factory_pass.

LaunchAgent already re-invokes the mill. A 180s heartbeat hosts one
factory pass, not the CLI multi-pass budget wrapper.
``--max-passes`` stays accepted for the organ CLI and is ignored.
"""

from __future__ import annotations

import argparse

from lokay.compose.factory import compose_factory_pass
from lokay.envelope import emit_exit
from lokay.proc._common import add_config_live


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-recovery-mill")
    add_config_live(parser)
    parser.add_argument("--max-passes", type=int, default=1)
    args = parser.parse_args(argv)
    # Domain failure is data for downstream recovery observation. The Fala
    # effector itself succeeds so conduction can always classify this run.
    mill = compose_factory_pass(
        config_path=args.config,
        live=bool(args.live),
    )
    return emit_exit({"ok": True, "mill": mill})


if __name__ == "__main__":
    raise SystemExit(main())
