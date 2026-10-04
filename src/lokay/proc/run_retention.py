"""Atomic: apply the lokay retention policy under a lokay home (t_2d81b9c3)."""

from __future__ import annotations

import argparse
from pathlib import Path

from lokay.envelope import emit_exit, err, ok


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-retention")
    parser.add_argument("--lokay-home")
    parser.add_argument("--max-age-days", type=float, default=14.0)
    parser.add_argument("--hard-cap-gb", type=float, default=10.0)
    parser.add_argument("--wrapper-keep", type=int, default=2)
    parser.add_argument("--journal-keep-last", type=int, default=5)
    parser.add_argument(
        "--skip-sqlite",
        action="store_true",
        help="filesystem classes only (no native journal maintenance)",
    )
    args = parser.parse_args(argv)
    try:
        if args.skip_sqlite:
            from lokay import retention

            result = retention.apply_filesystem_retention(
                Path(args.lokay_home).expanduser() if args.lokay_home else None,
                max_age_days=max(0.0, args.max_age_days),
                hard_cap_bytes=int(args.hard_cap_gb * 1024 * 1024 * 1024),
                wrapper_keep=max(0, args.wrapper_keep),
            )
        else:
            from lokay.fala_journal import maintain_lokay_fala_journals

            result = maintain_lokay_fala_journals(
                home=Path(args.lokay_home).expanduser() if args.lokay_home else None,
                max_age_days=max(0.0, args.max_age_days),
                hard_cap_bytes=int(args.hard_cap_gb * 1024 * 1024 * 1024),
                journal_keep_last=max(-1, args.journal_keep_last),
            )
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    return emit_exit(ok(**result))


if __name__ == "__main__":
    raise SystemExit(main())
