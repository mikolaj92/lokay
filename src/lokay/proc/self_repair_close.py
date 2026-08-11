"""Atomic: close the validated self-repair incident."""

from __future__ import annotations

import argparse

from lokay.proc import close_issue


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-self-repair-close")
    p.add_argument("--config", required=True)
    p.add_argument("--live", action="store_true")
    p.add_argument("--issue", required=True, type=int)
    p.add_argument("--commit", required=True)
    args = p.parse_args(argv)
    flags = ["--config", args.config]
    if args.live:
        flags.append("--live")
    return close_issue.main([
        *flags,
        "--repo", "mikolaj92/lokay",
        "--issue", str(args.issue),
        "--comment", f"Validated direct self-repair commit {args.commit} on main; restart required.",
    ])


if __name__ == "__main__":
    raise SystemExit(main())
