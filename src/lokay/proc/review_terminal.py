"""Emit one explicit terminal PR-review outcome."""

from __future__ import annotations

import argparse

from lokay.envelope import emit_exit, ok


def terminal_review(*, verdict: str, reason: str) -> dict[str, object]:
    return ok(terminal=True, verdict=verdict, reason=reason, needs_review=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-review-terminal")
    parser.add_argument("--verdict", required=True)
    parser.add_argument("--reason", required=True)
    args = parser.parse_args(argv)
    return emit_exit(terminal_review(verdict=args.verdict, reason=args.reason))


if __name__ == "__main__":
    raise SystemExit(main())
