from __future__ import annotations

import argparse
import sys

from lokay.safety import SafetyError, validate_argv

NODES = (
    "decide",
    "start",
    "unskip",
    "refresh-body",
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
    if args.node == "unskip":
        import json
        from lokay.start import skip_file
        from lokay.state import state_update

        unskip_parser = argparse.ArgumentParser(prog="lokay unskip")
        unskip_parser.add_argument("repo")
        unskip_parser.add_argument("issue", type=int)
        target = unskip_parser.parse_args(rest)
        if target.issue <= 0:
            unskip_parser.error("issue must be positive")
        path = skip_file()
        if path.is_file():
            try:
                data = json.loads(path.read_text())
                if not isinstance(data, dict):
                    raise ValueError("skip file must contain an object")
                bucket = data.get(target.repo, {})
                if not isinstance(bucket, dict):
                    raise ValueError("skip entries must contain an object")
                if str(target.issue) in bucket:
                    del bucket[str(target.issue)]
                    path.write_text(json.dumps(data))
            except (OSError, ValueError) as exc:
                print(f"unskip failed: {exc}", file=sys.stderr)
                return 1
        state_update(target.repo, target.issue, retry_at=0)
        print(json.dumps({"result": "unskipped", "repo": target.repo, "issue": target.issue}))
        return 0
    if args.node == "refresh-body":
        from lokay.start import main as start_main

        return start_main(["refresh-body", *rest])
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
