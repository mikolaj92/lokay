"""Atomic: fingerprint failures appended during one product mill run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lokay.envelope import emit_exit, err, ok
from lokay.recovery_history import observe_run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-recovery-observe")
    parser.add_argument("--state-path", required=True)
    parser.add_argument("--state-offset", required=True, type=int)
    parser.add_argument("--mill-json", required=True)
    args = parser.parse_args(argv)
    try:
        mill = json.loads(args.mill_json)
    except ValueError as exc:
        return emit_exit(err(f"invalid mill envelope: {exc}"))
    if not isinstance(mill, dict):
        return emit_exit(err("mill envelope must be an object"))
    observation = observe_run(
        state_path=Path(args.state_path),
        state_offset=args.state_offset,
        mill=mill,
    )
    return emit_exit(ok(observation=observation, mill=mill))


if __name__ == "__main__":
    raise SystemExit(main())
