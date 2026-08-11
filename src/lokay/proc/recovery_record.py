"""Atomic: append one run observation and evaluate the 4-of-5 quorum."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lokay.envelope import emit_exit, err, ok
from lokay.recovery_history import history_path_for, record_observation


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-recovery-record")
    parser.add_argument("--state-path", required=True)
    parser.add_argument("--observation-json", required=True)
    args = parser.parse_args(argv)
    try:
        observation = json.loads(args.observation_json)
    except ValueError as exc:
        return emit_exit(err(f"invalid recovery observation: {exc}"))
    if not isinstance(observation, dict):
        return emit_exit(err("recovery observation must be an object"))
    confirmed = record_observation(
        history_path_for(Path(args.state_path)), observation
    )
    return emit_exit(
        ok(
            confirmed=confirmed is not None,
            recovery=confirmed or {},
            observation=observation,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
