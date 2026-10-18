from __future__ import annotations

import argparse
import difflib
import gzip
import hashlib
import json
import re
import sys
from json import dumps
from pathlib import Path

from lokay import graph
from lokay.types import Run, parse_event


def unpack(value, home: Path, *, source: Path | None = None):
    if not isinstance(value, dict) or set(value) != {"blob"}:
        return value
    reference = value["blob"]
    if source is None:
        if not isinstance(reference, str) or not re.fullmatch(r"(?:sha256:)?[a-f0-9]{64}", reference):
            raise ValueError("invalid blob hash")
        sha = reference.removeprefix("sha256:")
        candidates = [home / "ticks/blobs" / sha, home / "blobs" / sha[:2] / sha]
    else:
        if not isinstance(reference, str) or not reference.startswith("sha256:"):
            raise ValueError("invalid blob hash")
        sha = reference[7:]
        if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            raise ValueError("invalid blob hash")
        candidates = [home / "blobs" / sha, home / "ticks" / "blobs" / sha]
        if source.is_dir():
            candidates.append(source / "blobs" / sha)
    candidates = [variant for candidate in candidates
                  for variant in (candidate, candidate.with_suffix(".gz"))]
    blob = next((candidate for candidate in candidates if candidate.is_file()), None)
    if blob is None:
        if source is None:
            return None
        blob = candidates[0]
    raw = blob.read_bytes()
    if blob.suffix == ".gz":
        raw = gzip.decompress(raw)
    if hashlib.sha256(raw).hexdigest() != sha:
        raise ValueError("blob hash mismatch")
    return json.loads(raw)


def main(argv: list[str]) -> int:
    replay = argparse.ArgumentParser(prog="lokay replay")
    replay.add_argument("path", type=Path, nargs="?", default=Path("fixtures"))
    replay.add_argument("--repo")
    replay.add_argument("--issue", type=int)
    filters = replay.parse_args(argv)
    source = filters.path
    paths = sorted(path for path in source.rglob("*")
                   if path.name.endswith((".jsonl", ".jsonl.gz"))) if source.is_dir() else [source]
    count = 0
    ticks = 0
    row = {}
    try:
        if not paths:
            raise ValueError("no replay files")
        for path in paths:
            if not path.name.endswith((".jsonl", ".jsonl.gz")):
                raise ValueError("expected .jsonl or .jsonl.gz")
            if path.with_suffix(".json").is_file():
                from lokay.effects.replay import Mismatch, segment

                with path.open() as stream:
                    rows = [json.loads(line) for line in stream]
                if any(value is not None and rows[0].get(key) != value for key, value in
                       (("repo", filters.repo), ("issue", filters.issue))):
                    continue
                try:
                    segment(path, rows)
                except Mismatch as exc:
                    raise ValueError(f"{path}: {exc}") from None
                ticks += 1
                continue
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
                        row[key] = unpack(row[key], path.parent, source=source)
                    if any(not isinstance(row[key], dict) for key in ("before", "event", "after")):
                        raise ValueError("expected before/event/after objects")
                    from lokay.effects.replay import compatible_state

                    got = graph.step(Run.from_state(row["before"]), parse_event(row["event"])).state
                    got = {key: value for key, value in got.items() if key != "updated_at"}
                    expected = {key: value for key, value in row["after"].items() if key != "updated_at"}
                    got = compatible_state(got, expected)
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
    if ticks:
        print(f"replay: {ticks}/{ticks} tick segments ok")
    return 0
