from __future__ import annotations

import argparse
import sys

from lokay.safety import SafetyError, validate_argv

NODES = (
    "decide",
    "start",
    "refresh-body",
    "status",
    "monitor",
    "replay",
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
    if args.node == "refresh-body":
        from lokay.start import main as start_main

        return start_main(["refresh-body", *rest])
    if args.node == "replay":
        import gzip
        import json
        from datetime import datetime, timezone
        from lokay.state import RUNS

        replay = argparse.ArgumentParser(prog="lokay replay")
        replay.add_argument("--tick")
        replay.add_argument("--repo")
        replay.add_argument("--issue", type=int)
        replay.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
        filters = replay.parse_args(rest)
        day = datetime.strptime(filters.date, "%Y-%m-%d").strftime("%Y-%m-%d")
        directory = RUNS.parent / "ticks"
        path = directory / f"{day}.jsonl"
        if not path.exists():
            path = path.with_suffix(".jsonl.gz")
        states = {}
        sequences = {}
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt") as stream:
            for line in stream:
                row = json.loads(line)
                if any(value is not None and row.get(key) != value for key, value in
                       (("tick", filters.tick), ("repo", filters.repo), ("issue", filters.issue))):
                    continue
                tick = row["tick"]
                if row["v"] != 1 or row["seq"] <= sequences.get(tick, 0):
                    raise ValueError("invalid event sequence")
                sequences[tick] = row["seq"]
                for key in ("before", "after", "output"):
                    value = row.get(key)
                    if isinstance(value, dict) and set(value) == {"blob"}:
                        sha = value["blob"].removeprefix("sha256:")
                        if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
                            raise ValueError("invalid blob hash")
                        import hashlib

                        raw = (directory / "blobs" / sha).read_bytes()
                        if hashlib.sha256(raw).hexdigest() != sha:
                            raise ValueError("blob hash mismatch")
                        row[key] = json.loads(raw)
                if row["kind"] == "transition":
                    identity = (row["repo"], row["issue"])
                    if states.get(identity, row["before"]) != row["before"]:
                        raise ValueError("state discontinuity")
                    states[identity] = row["after"]
                print(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
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
