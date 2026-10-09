from __future__ import annotations

import argparse
import sys

from lokay2.safety import SafetyError, validate_argv

NODES = (
    "decide",
    "start",
    "plan-write",
    "plan-check",
    "build-code",
    "build-publish",
    "check-ci",
    "check-scope",
    "check-tests",
    "check-correctness",
    "check-aggregate",
    "fix-code",
    "fix-publish",
    "merge",
)


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(prog="lokay2")
    parser.add_argument("node", nargs="?", choices=NODES)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--probe", action="store_true")
    args, rest = parser.parse_known_args(raw)
    try:
        validate_argv(["lokay2", *raw])
    except SafetyError as exc:
        print(f"rejected: {exc}", file=sys.stderr)
        return 2
    if args.node is None:
        parser.print_help()
        return 0
    if args.node == "start":
        from lokay2.start import main as start_main

        return start_main(["--check"] if args.check else rest)
    if args.node == "decide":
        from lokay2.decide import main as decide_main

        if args.probe:
            sys.argv = ["lokay2", "--probe"]
        return decide_main()
    from lokay2.nodes import COMMANDS

    return COMMANDS[args.node]()


if __name__ == "__main__":
    raise SystemExit(main())
