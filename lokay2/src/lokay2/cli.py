from __future__ import annotations

import argparse
import sys

from lokay2.safety import SafetyError, validate_argv


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay2")
    parser.add_argument("node", nargs="?", choices=["decide", "start"])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        validate_argv(["lokay2", *(argv if argv is not None else sys.argv[1:])])
    except SafetyError as exc:
        print(f"rejected: {exc}", file=sys.stderr)
        return 2
    if args.node is None:
        parser.print_help()
        return 0
    print("not implemented", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
