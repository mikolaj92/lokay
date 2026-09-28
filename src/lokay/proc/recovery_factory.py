"""Atomic subprocess boundary: execute one parent factory_pass.

LaunchAgent already re-invokes the lokay. A 180s heartbeat hosts one
factory pass, not the CLI multi-pass budget wrapper.
``--max-passes`` stays accepted for the organ CLI and is ignored.
"""

from __future__ import annotations

import argparse

from lokay.compose.factory import compose_factory_pass
from lokay.envelope import emit_exit
from lokay.proc._common import add_config_live


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-recovery-factory")
    add_config_live(parser)
    parser.add_argument("--max-passes", type=int, default=1)
    args = parser.parse_args(argv)
    # Domain failure is data for downstream recovery observation. The Fala
    # effector itself succeeds so conduction can always classify this run.
    result = compose_factory_pass(
        config_path=args.config,
        live=bool(args.live),
    )
    # Downstream summarize only needs the factory verdict, not its full 30+ MiB
    # Fala effector journal. Keep the detailed result on its own journal.
    factory = {
        key: result[key]
        for key in ("ok", "health", "reason", "kind", "engine", "planned", "progress", "outcome", "pass_receipt_path")
        if key in result
    }
    factory["db"] = result.get("db")
    factory["run_id"] = result.get("run_id")
    return emit_exit({"ok": True, "factory": factory})


if __name__ == "__main__":
    raise SystemExit(main())
