"""Atomic: rotate oversized mill Fala sqlite journals."""

from __future__ import annotations

import argparse
from pathlib import Path

from lokay.envelope import emit_exit, err, ok
from lokay.fala_journal import DEFAULT_MIN_BYTES, KEEP_ROTATED, rotate_mill_fala_journals


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-rotate-fala-journals")
    parser.add_argument("--lokay-home")
    parser.add_argument("--min-bytes", type=int, default=DEFAULT_MIN_BYTES)
    parser.add_argument("--keep", type=int, default=KEEP_ROTATED)
    args = parser.parse_args(argv)
    try:
        result = rotate_mill_fala_journals(
            home=Path(args.lokay_home) if args.lokay_home else None,
            min_bytes=max(0, int(args.min_bytes)),
            keep=max(0, int(args.keep)),
        )
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    return emit_exit(ok(**result))


if __name__ == "__main__":
    raise SystemExit(main())
