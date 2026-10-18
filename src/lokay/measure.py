from __future__ import annotations

import argparse
import gzip
import json
import math
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lokay import config
from lokay.dashboard import kind
from lokay.effects.git import commit_time, merge_files
from lokay.replay import unpack


def utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("expected an ISO-8601 UTC time")
    return parsed


def boundary(value: str) -> datetime:
    if re.match(r"^\d{4}-\d\d-\d\d", value):
        return utc(value)
    return datetime.fromisoformat(commit_time(Path(__file__).resolve().parents[2], value)).astimezone(timezone.utc)


def changed_files(value, home: Path):
    value = unpack(value, home)
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return None
    if isinstance(value, dict):
        for key in ("files", "changed_files"):
            files = value.get(key)
            if isinstance(files, list) and not files:
                return []
            if isinstance(files, list):
                normalized = [{"path": item} if isinstance(item, str) else item for item in files]
                if kind(normalized) != "?":
                    return normalized
        for child in value.values():
            found = changed_files(child, home)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = changed_files(child, home)
            if found is not None:
                return found
    return None


def merges(home: Path, ticks: list[datetime] | None = None) -> list[dict]:
    rows = []
    for path in sorted((home / "ticks").glob("*.jsonl*")):
        if not path.name.endswith((".jsonl", ".jsonl.gz")):
            continue
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt") as stream:
            for line in stream:
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError("expected tick object")
                if ticks is not None:
                    ticks.append(utc(row["ts"]))
                if row.get("kind") in ("call", "transition") and row.get("repo") and row.get("issue"):
                    rows.append((utc(row["ts"]), row))
    evidence = {}
    repos = None
    seen = set()
    result = []
    for timestamp, row in sorted(rows, key=lambda item: item[0]):
        key = (row["repo"], row["issue"])
        files = changed_files({name: row[name] for name in ("output", "before", "after", "event") if name in row}, home)
        if files is not None:
            evidence[key] = files
        if row["kind"] != "transition" or row.get("node") != "merge":
            continue
        event = unpack(row.get("event"), home)
        fields = event.get("fields", {}) if isinstance(event, dict) else {}
        if not isinstance(fields, dict) or fields.get("result") != "merged":
            continue
        sha = fields.get("sha")
        if not isinstance(sha, str) or not sha.strip() or key in seen:
            continue
        files = evidence.get(key)
        if repos is None:
            repos = {repo["name"]: Path(repo["clone_path"]).expanduser() for repo in config.load_repos()}
        clone = repos.get(row["repo"])
        if clone is not None:
            merged_files = merge_files(clone, sha)
            if merged_files is not None:
                files = merged_files
        if files == []:
            continue
        seen.add(key)
        change = kind(files)
        result.append({"time": timestamp, "kind": "code" if change not in ("docs", "lokay") else change,
                       "unknown_kind": change == "?"})
    return result


def window(label: str, start: datetime, end: datetime, records: list[dict]) -> dict:
    hours = (end - start).total_seconds() / 3600
    if not math.isfinite(hours) or hours <= 0:
        raise ValueError("window end must be after its start")
    selected = [row for row in records if start <= row["time"] < end]
    code = sum(row["kind"] == "code" for row in selected)
    docs = sum(row["kind"] == "docs" for row in selected)
    return {"label": label, "start": start.isoformat(), "until": end.isoformat(), "hours": hours,
            "code": code, "docs": docs, "code/h": code / hours, "docs/h": docs / hours,
            "unknown_kind": sum(row["unknown_kind"] for row in selected)}


def segment(name: str, data: dict) -> str:
    text = (f"{name}={data['label']} code/h={data['code/h']:.2f} docs/h={data['docs/h']:.2f} "
            f"n={data['code']}/{data['docs']} hours={data['hours']:g}")
    return text + (f" unknown_kind={data['unknown_kind']}" if data["unknown_kind"] else "")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="lokay measure")
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--since", required=True)
    parser.add_argument("--until")
    parser.add_argument("--baseline-until")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        start_a, start_b = boundary(args.baseline), boundary(args.since)
        end_a = boundary(args.baseline_until) if args.baseline_until else start_b
        end_b = boundary(args.until) if args.until else datetime.now(timezone.utc)
        window(args.baseline, start_a, end_a, [])
        window(args.since, start_b, end_b, [])
        ticks = []
        records = merges(config.HOME, ticks)
        for name, start, end in (("A", start_a, end_a), ("B", start_b, end_b)):
            if not any(start <= timestamp < end for timestamp in ticks):
                raise ValueError(f"no ticks for window {name} {start.isoformat()}..{end.isoformat()}")
        a = window(args.baseline, start_a, end_a, records)
        b = window(args.since, start_b, end_b, records)
        verdict = "keep" if b["code/h"] >= a["code/h"] else "revert"
        print(json.dumps({"A": a, "B": b, "verdict": verdict}) if args.json else
              f"measure {segment('A', a)} | {segment('B', b)} | verdict={verdict}")
        return 0
    except (OSError, ValueError, KeyError, TypeError, OverflowError) as exc:
        print(f"measure: {exc}", file=sys.stderr)
        return 2
