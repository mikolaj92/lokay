from __future__ import annotations

import argparse
import sys

from lokay.safety import SafetyError, validate_argv

NODES = (
    "decide",
    "start",
    "status",
    "monitor",
)


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(prog="lokay")
    parser.add_argument("node", nargs="?", choices=NODES)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--probe", action="store_true")
    args, rest = parser.parse_known_args(raw)
    try:
        validate_argv(["lokay", *raw])
    except SafetyError as exc:
        print(f"rejected: {exc}", file=sys.stderr)
        return 2
    if args.node is None:
        parser.print_help()
        return 0
    if args.node == "status":
        from lokay.observe import status

        status()
        return 0
    if args.node == "monitor":
        import json
        from lokay.observe import monitor

        print(json.dumps(monitor()))
        return 0
    if args.node == "start":
        from lokay.start import main as start_main
        from lokay.observe import ticking

        if args.check:
            return start_main(["--check"])
        with ticking():
            return start_main(rest)
    if args.node == "decide":
        from lokay.decide import main as decide_main

        if args.probe:
            sys.argv = ["lokay", "--probe"]
        return decide_main()


if __name__ == "__main__":
    raise SystemExit(main())
