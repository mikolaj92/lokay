"""Atomic: pick one issue from stdin JSON list → JSON."""

from __future__ import annotations

import argparse

from lokay.envelope import emit_exit, err, ok, read_stdin_json
from lokay.models import Issue


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-select-issue")
    p.add_argument("--strategy", default="oldest", choices=("oldest", "newest"))
    args = p.parse_args(argv)
    payload = read_stdin_json()
    if not isinstance(payload, dict):
        return emit_exit(err("stdin must be JSON object with issues[]"))
    raw = payload.get("issues") or []
    if not raw:
        return emit_exit(ok(selected=None, reason="empty"))
    issues = [Issue.from_dict(x) for x in raw]
    issues.sort(key=lambda i: i.number, reverse=(args.strategy == "newest"))
    chosen = issues[0]
    return emit_exit(ok(selected=chosen.to_dict(), strategy=args.strategy))


if __name__ == "__main__":
    raise SystemExit(main())
