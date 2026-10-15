from __future__ import annotations

from json import dumps

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
    "lint",
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
    if args.node == "lint":
        from pathlib import Path
        from lokay.lint import lint

        command = argparse.ArgumentParser(prog="lokay lint")
        command.add_argument("base")
        command.add_argument("head")
        refs = command.parse_args(rest)
        try:
            errors = lint(refs.base, refs.head, Path.cwd())
        except ValueError as exc:
            print(f"lint: {exc}", file=sys.stderr)
            return 1
        for error in errors:
            print(error)
        return int(bool(errors))
    if args.node == "replay":
        import gzip
        import json
        import difflib
        import hashlib
        from pathlib import Path
        from lokay.start import step

        replay = argparse.ArgumentParser(prog="lokay replay")
        replay.add_argument("path", type=Path)
        replay.add_argument("--repo")
        replay.add_argument("--issue", type=int)
        filters = replay.parse_args(rest)
        source = filters.path
        paths = sorted(path for path in source.rglob("*")
                       if path.name.endswith((".jsonl", ".jsonl.gz"))) if source.is_dir() else [source]
        count = 0
        row = {}
        try:
            if not paths:
                raise ValueError("no replay files")
            for path in paths:
                if not path.name.endswith((".jsonl", ".jsonl.gz")):
                    raise ValueError("expected .jsonl or .jsonl.gz")
                opener = gzip.open if path.suffix == ".gz" else open
                with opener(path, "rt") as stream:
                    for line in stream:
                        value = json.loads(line)
                        if not isinstance(value, dict):
                            raise ValueError("expected event object")
                        row = value
                        if row.get("kind") != "transition" or any(
                            value is not None and row.get(key) != value for key, value in
                            (("repo", filters.repo), ("issue", filters.issue))
                        ):
                            continue
                        for key in ("before", "event", "after"):
                            value = row[key]
                            if isinstance(value, dict) and set(value) == {"blob"}:
                                reference = value["blob"]
                                if not isinstance(reference, str) or not reference.startswith("sha256:"):
                                    raise ValueError("invalid blob hash")
                                sha = reference[7:]
                                if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
                                    raise ValueError("invalid blob hash")
                                candidates = [path.parent / "blobs" / sha,
                                              path.parent / "ticks" / "blobs" / sha]
                                if source.is_dir():
                                    candidates.append(source / "blobs" / sha)
                                candidates = [variant for candidate in candidates
                                              for variant in (candidate, candidate.with_suffix(".gz"))]
                                blob = next((candidate for candidate in candidates if candidate.is_file()), candidates[0])
                                raw = gzip.decompress(blob.read_bytes()) if blob.suffix == ".gz" else blob.read_bytes()
                                if hashlib.sha256(raw).hexdigest() != sha:
                                    raise ValueError("blob hash mismatch")
                                row[key] = json.loads(raw)
                        if any(not isinstance(row[key], dict) for key in ("before", "event", "after")):
                            raise ValueError("expected before/event/after objects")
                        got = step(row["before"], row["event"])
                        got = {key: value for key, value in got.items() if key != "updated_at"}
                        expected = {key: value for key, value in row["after"].items() if key != "updated_at"}
                        if got != expected:
                            print(f"replay: mismatch seq={row.get('seq')} node={row.get('node')} "
                                  f"event={dumps(row['event'], ensure_ascii=False)}", file=sys.stderr)
                            print("\n".join(difflib.unified_diff(
                                dumps(expected, sort_keys=True, indent=2, ensure_ascii=False).splitlines(),
                                dumps(got, sort_keys=True, indent=2, ensure_ascii=False).splitlines(),
                                fromfile="expected", tofile="got", lineterm="")), file=sys.stderr)
                            return 1
                        count += 1
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f"replay: seq={row.get('seq')} node={row.get('node')} "
                  f"event={row.get('event')} error={exc}", file=sys.stderr)
            return 1
        print(f"replay: {count}/{count} transitions ok")
        return 0
    if args.node == "status":
        from lokay.observe import status

        status()
        return 0
    if args.node == "monitor":
        import json
        from lokay.observe import monitor

        print(dumps(monitor()))
        return 0
    if args.node == "start":
        from lokay.start import main as start_main
        from lokay.observe import ticking

        if args.check:
            return start_main(["--check"])
        with ticking():
            return start_main(rest)
    if args.node == "decide":
        from lokay.effects.decide import main as decide_main

        if args.probe:
            sys.argv = ["lokay", "--probe"]
        return decide_main()


if __name__ == "__main__":
    raise SystemExit(main())
