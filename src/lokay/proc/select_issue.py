"""Atomic: pick one issue from stdin JSON list → JSON.

Skips numbers listed in stdin `exclude` or repeated `--exclude N` so a stuck
issue cannot monopolize every tick.
"""

from __future__ import annotations

import argparse

from lokay.envelope import emit_exit, err, ok, read_stdin_json
from lokay.models import Issue


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-select-issue")
    p.add_argument("--strategy", default="oldest", choices=("oldest", "newest"))
    p.add_argument(
        "--exclude",
        action="append",
        type=int,
        default=[],
        help="issue number to skip (repeatable)",
    )
    args = p.parse_args(argv)
    payload = read_stdin_json()
    if not isinstance(payload, dict):
        return emit_exit(err("stdin must be JSON object with issues[]"))
    raw = payload.get("issues") or []
    if not raw:
        return emit_exit(ok(selected=None, reason="empty"))
    exclude: set[int] = set(int(x) for x in (args.exclude or []) if x is not None)
    for x in payload.get("exclude") or []:
        try:
            exclude.add(int(x))
        except (TypeError, ValueError):
            continue
    issues = [Issue.from_dict(x) for x in raw]
    issues = [i for i in issues if i.number not in exclude]
    if not issues:
        return emit_exit(ok(selected=None, reason="all_excluded", exclude=sorted(exclude)))
    issues.sort(key=lambda i: i.number, reverse=(args.strategy == "newest"))
    chosen = issues[0]
    return emit_exit(
        ok(
            selected=chosen.to_dict(),
            strategy=args.strategy,
            exclude=sorted(exclude),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
