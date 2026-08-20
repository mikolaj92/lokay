"""Atomic: compact the existing durable state JSONL."""

from __future__ import annotations

import argparse
from pathlib import Path

from lokay.config import load_config
from lokay.envelope import emit_exit, err, ok
from lokay.state_compact import compact_state


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-compact-state")
    parser.add_argument("--config")
    parser.add_argument("--min-bytes", type=int, default=8 * 1024 * 1024)
    args = parser.parse_args(argv)
    try:
        cfg = load_config(args.config)
        result = compact_state(Path(cfg.state_path), min_bytes=max(0, args.min_bytes))
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    return emit_exit(ok(state_path=str(cfg.state_path), **result))


if __name__ == "__main__":
    raise SystemExit(main())
