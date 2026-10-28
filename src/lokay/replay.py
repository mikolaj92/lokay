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


def extract(source: Path, directory: Path, repo: str, issue: int, prefix: str) -> None:
    from tempfile import TemporaryDirectory
    from lokay import store

    opener = gzip.open if source.suffix == ".gz" else open
    with opener(source, "rt") as stream:
        rows = [row for line in stream if (row := json.loads(line)).get("repo") == repo
                and row.get("issue") == issue and row.get("tick", "").startswith(prefix)]
    if len({row["tick"] for row in rows}) != 1:
        raise ValueError("tick prefix must select exactly one tick/repo/issue")
    if any(row.get("call") == "pi" for row in rows):
        raise ValueError("choose a tick without pi calls")
    rows.sort(key=lambda row: row["seq"])
    if len({row["seq"] for row in rows}) != len(rows):
        raise ValueError("duplicate tick sequence")
    for row in rows:
        for key in ("effect", "before", "event", "after"):
            if key in row:
                row[key] = unpack(row[key], source.parent, source=source.parent)
    transitions = [row for row in rows if row["kind"] == "transition"]
    first = next((row for row in transitions if row["before"].get("node") == "check"
                  and row["event"].get("fields", {}).get("tested") is False
                  and "local_ci" in row["event"].get("fields", {})), None)
    if first is None:
        raise ValueError("no Check local-test boundary")
    last = next((row for row in transitions if row["seq"] > first["seq"]
                 and row["event"].get("action") == "verdict"), None)
    if last is None or last["event"]["outcome"].get("result") not in ("fix", "merge"):
        raise ValueError("no Check fix or merge verdict")
    calls = [row["effect"] for row in rows if row["kind"] == "call" and row["seq"] <= last["seq"]]
    if any("requests" not in effect and "argv" not in effect for effect in calls):
        raise ValueError("unsupported recorded call")
    ci = next(row["event"]["fields"]["local_ci"] for row in transitions
              if first["seq"] < row["seq"] <= last["seq"]
              and row["event"].get("fields", {}).get("local_ci"))
    tests = ci["argv"]
    worktree = Path(ci["tested_cwds"][0])
    roots = [effect["attempts"][-1]["stdout"].strip() for effect in calls
             if effect.get("argv") == ["git", "rev-parse", "--show-toplevel"]]
    root = next(Path(value) for value in roots if value != str(worktree))
    diffs = [effect for effect in calls if effect.get("argv", [])[:2] == ["git", "diff"]
             and len(effect["argv"]) == 3 and "...HEAD" in effect["argv"][2]]
    diff = diffs[-1]["attempts"][-1]["stdout"]
    base = diffs[-1]["argv"][2].removeprefix("origin/").removesuffix("...HEAD")
    gh = next(effect["argv"][0] for effect in calls if Path(effect.get("argv", [""])[0]).name == "gh")
    decision_effect = next((effect for effect in calls if "requests" in effect), None)
    if decision_effect is None:
        home = Path("/home/lokay")
        run = home / "runs" / repo / str(issue)
        wire = {}
    else:
        decision = decision_effect["input"]["state"]
        wire = decision_effect["requests"][0]["body"]
        run = Path(decision["diff_path"]).parent
        home = run.parents[2]
    diff_path = str(run / "check-input.patch")
    test_outputs = [row["effect"]["attempts"][-1] for row in rows
                    if first["seq"] < row["seq"] < last["seq"] and row.get("call")
                    and row["effect"].get("argv") == tests]
    test_log = "\n".join(attempt["stdout"] + attempt["stderr"] for attempt in test_outputs)
    if not ci["log"].endswith("\n" + test_log):
        raise ValueError("local-test log does not match recorded output")
    setup = {"log": ci["log"][:-(len(test_log) + 1)], "failed": []}
    contents = {}
    for effect in calls:
        argv = effect.get("argv", [])
        if not argv or argv[0] != "git":
            continue
        output = effect["attempts"][-1]
        if output["returncode"]:
            continue
        if argv[1:] == ["ls-files", "-z"] or argv[1:5] == ["ls-tree", "-r", "--name-only", "-z"]:
            for name in output["stdout"].split("\0"):
                if name:
                    contents.setdefault(str(worktree / name), "")
        if argv[1:2] == ["show"] and len(argv) == 3 and argv[2].startswith("HEAD:"):
            contents[str(worktree / argv[2][5:])] = output["stdout"]
    from lokay.lint import diff_lines

    lock_lines = {}
    for name, number, kind, text in diff_lines(diff):
        if kind == "+" and Path(name).name == "uv.lock":
            lock_lines.setdefault(str(worktree / name), []).append(text)
    for target, lines in lock_lines.items():
        if not contents.get(target):
            contents[target] = "\n".join(lines) + "\n"
    contents[diff_path] = diff
    contents[str(root / ".git/HEAD")] = f"ref: refs/heads/{base}\n"
    contents[str(worktree / ".git")] = f"gitdir: {root}/.git/worktrees/{worktree.name}\n"
    for effect in calls:
        argv = effect.get("argv", [])
        if argv[1:3] == ["pr", "edit"] and "--body" in argv:
            body = argv[argv.index("--body") + 1]
            contents[str(run / "plan.md")] = body.split("\n\n", 1)[1].split("\n\n## Zmienione pliki", 1)[0]
            break
    selected = [row for row in rows if first["seq"] <= row["seq"] <= last["seq"]
                and row["kind"] in ("call", "transition")]
    manifest = {"entry": "check", "api": "chat" if "messages" in wire else "tensorfold" if "input" in wire else "mini",
                "model": wire.get("model", "") if wire else "", "repo": {"name": repo, "clone_path": str(root), "test": tests,
                "merge": "on", "syntax_only": ci.get("syntax_only", False)}, "issue": issue,
                "gh": gh, "time": first["event"]["ts"], "paths": {str(home): "home/.lokay",
                str(root.parent): "worktree"}, "before": first["before"], "base": base,
                "setup": setup, "diff_path": diff_path, "outcome": last["event"]["outcome"],
                "diff": "diff.patch", "uv": next((effect["argv"][0] for effect in calls
                if Path(effect.get("argv", [""])[0]).name == "uv"), "uv")}
    with TemporaryDirectory(prefix="lokay-extract-") as temporary:
        staging = Path(temporary)
        files = {}
        for index, (target, text) in enumerate(contents.items()):
            if not any(Path(target).is_relative_to(old) for old in manifest["paths"]):
                raise ValueError("recorded file escapes sandbox paths")
            name = "diff.patch" if target == diff_path else f"file-{index}.txt"
            store.write_artifact(staging / name, text)
            files[target] = name
        store.write_segment(directory, staging, {**manifest, "files": files}, selected)


SOURCES = ("escape_check", "revert", "reopen", "red_main", "fix_pr", "clean")


def bad_case(case: Path) -> tuple[Path, dict]:
    meta = json.loads(case.read_text())
    if meta.get("source") not in SOURCES or meta.get("expected") not in ("fix", "merge"):
        raise ValueError(f"invalid bad case {case}")
    segment_path = case.parent / meta.get("segment", "segment.jsonl")
    if not segment_path.is_file():
        raise ValueError(f"missing bad case segment {segment_path}")
    return segment_path, meta


def main(argv: list[str]) -> int:
    replay = argparse.ArgumentParser(prog="lokay replay")
    replay.add_argument("path", type=Path, nargs="?", default=Path("fixtures"))
    mode = replay.add_mutually_exclusive_group()
    mode.add_argument("--rerecord", type=Path)
    mode.add_argument("--extract", type=Path)
    replay.add_argument("--tick")
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
        if filters.extract is not None:
            if not filters.repo or filters.issue is None or not filters.tick or source.is_dir():
                raise ValueError("--extract requires a log file, --repo, --issue and --tick")
            extract(source, filters.extract, filters.repo, filters.issue, filters.tick)
            print(f"replay: extracted {filters.extract}")
            return 0
        if filters.tick is not None:
            raise ValueError("--tick requires --extract")
        cases = sorted(source.glob("*/case.json")) if source.is_dir() else []
        if cases:
            from lokay import store
            from lokay.effects.replay import Mismatch, segment

            if filters.rerecord is not None:
                if filters.rerecord.exists():
                    raise ValueError("--rerecord directory already exists")
                for case in cases:
                    segment_path, meta = bad_case(case)
                    with segment_path.open() as stream:
                        rows = [json.loads(line) for line in stream]
                    target = filters.rerecord / case.parent.name
                    segment(segment_path, rows, rerecord=target)
                    store.write_json(target / "case.json", {**meta, "segment": "segment.jsonl"})
                print(f"replay: re-recorded {len(cases)} bad cases")
                return 0
            for case in cases:
                segment_path, meta = bad_case(case)
                with segment_path.open() as stream:
                    rows = [json.loads(line) for line in stream]
                try:
                    outcome = segment(segment_path, rows)
                except Mismatch as exc:
                    raise ValueError(f"{case}: {exc}") from None
                if outcome.get("result") != meta["expected"]:
                    print(f"replay: {case} expected {meta['expected']} got {outcome.get('result')}",
                          file=sys.stderr)
                    return 1
                ticks += 1
            print(f"replay: {ticks} bad cases ok")
            return 0
        if filters.rerecord is not None and (source.is_dir() or not source.with_suffix(".json").is_file()):
            raise ValueError("--rerecord requires a single segment path")
        if filters.rerecord is not None and filters.rerecord.exists():
            raise ValueError("--rerecord directory already exists")
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
                    segment(path, rows, rerecord=filters.rerecord)
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
    except (OSError, ValueError, KeyError, TypeError, StopIteration, IndexError) as exc:
        print(f"replay: seq={row.get('seq')} node={row.get('node')} "
              f"event={row.get('event')} error={exc}", file=sys.stderr)
        return 1
    print(f"replay: {count}/{count} transitions ok")
    if ticks:
        print(f"replay: {ticks}/{ticks} tick segments ok, 0 retired")
    return 0
