"""Atomic: capture the state-log boundary before one product mill run."""

from __future__ import annotations

import argparse

from lokay.envelope import emit_exit, ok
from lokay.proc._common import add_config_live, load_cfg


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-recovery-begin")
    add_config_live(parser)
    args = parser.parse_args(argv)
    state_path = load_cfg(args).state_path
    try:
        offset = state_path.stat().st_size
    except OSError:
        offset = 0
    return emit_exit(ok(state_path=str(state_path), state_offset=offset))


if __name__ == "__main__":
    raise SystemExit(main())
