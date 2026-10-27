from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

from lokay import store
from lokay.replay import unpack
from lokay.types import Finding, parse_finding


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def timestamp(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timestamps require an explicit timezone")
    return result


def classify(finding: dict, evidence: list[dict]) -> dict:
    linked = [row for row in evidence if row.get("finding") == finding["id"]
              and row.get("sha") == finding["sha"] and row.get("source")]
    signals = set()
    gaps = []
    times = {digest(row): timestamp(row["ts"]) for row in linked}
    merges = [row for row in linked if row.get("kind") == "merge"]
    location = parse_finding(finding["finding"])
    corrections = [row for row in linked if row.get("kind") == "correction"
                   and isinstance(location, Finding) and row.get("path") == location.plik
                   and type(row.get("start")) is int and type(row.get("end")) is int
                   and type(location.linia_od) is int and type(location.linia_do) is int
                   and row["start"] <= location.linia_od <= location.linia_do <= row["end"]
                   and row.get("corrected_sha") and row["corrected_sha"] != finding["sha"]]
    if any(row.get("kind") in ("dispute", "no_changes") for row in linked):
        signals.add("false_alarm")
    escapes = [row for row in linked if row.get("kind") in ("revert", "reopen", "red_main")
               and any(row.get("merge_sha") == merge.get("merge_sha")
                       and merge.get("merge_sha") and times[digest(row)] >= times[digest(merge)]
                       for merge in merges)]
    if escapes:
        signals.add("escape")
    chronology = any(time < timestamp(finding["ts"]) for time in times.values())
    stable = False
    for correction in corrections:
        fixed = times[digest(correction)]
        if fixed < timestamp(finding["ts"]):
            chronology = True
            continue
        for merge in merges:
            merged = times[digest(merge)]
            if merge.get("head_sha") != correction["corrected_sha"]:
                continue
            if merged < fixed:
                chronology = True
                continue
            deadline = merged + timedelta(hours=48)
            covered = any(row.get("kind") == "coverage"
                          and row.get("merge_sha") == merge.get("merge_sha")
                          and row.get("complete") is True
                          and set(row.get("events", [])) >= {"revert", "reopen"}
                          and timestamp(row["since"]) <= merged
                          and times[digest(row)] >= deadline for row in linked)
            reverted = any(row.get("kind") in ("revert", "reopen")
                           and row.get("merge_sha") == merge.get("merge_sha")
                           and merged <= times[digest(row)] <= deadline for row in linked)
            if covered and not reverted:
                stable = True
    if stable:
        signals.add("true_error")
    if not corrections:
        gaps.append("indicated_lines_correction")
    if not merges:
        gaps.append("linked_merge")
    if not stable:
        gaps.append("stable_48h_observation")
    if not linked:
        gaps.append("outcome_evidence")
    label = "ambiguous" if len(signals) > 1 or chronology else next(iter(signals), "incomplete")
    return {"label": label, "signals": sorted(signals), "gaps": gaps if label == "incomplete" else [],
            "chronology_conflict": chronology, "evidence": linked}


def corpus(source: Path, since: datetime, until: datetime, evidence: list[dict], expected: int) -> dict:
    if until <= since:
        raise ValueError("until must follow since")
    paths = sorted(path for path in source.rglob("*") if path.name.endswith((".jsonl", ".jsonl.gz"))) if source.is_dir() else [source]
    if not paths:
        raise ValueError("no local tick logs")
    rows = []
    sources = []
    identities = set()
    for path in paths:
        sources.append({"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt") as stream:
            for number, line in enumerate(stream, 1):
                row = json.loads(line)
                identity = (row["tick"], row["seq"])
                if identity in identities:
                    raise ValueError("duplicate tick sequence")
                identities.add(identity)
                rows.append((timestamp(row["ts"]), row, path, number))
    rows.sort(key=lambda item: (item[0], item[1]["tick"], item[1]["seq"]))
    pending = {}
    rounds = []
    finished = set()

    def resolve(value, path, missing):
        if isinstance(value, dict):
            if set(value) == {"blob"}:
                try:
                    return resolve(unpack(value, path.parent, source=path.parent), path, missing)
                except FileNotFoundError:
                    missing.append(value["blob"])
                    return value
            return {key: resolve(item, path, missing) for key, item in value.items()}
        if isinstance(value, list):
            return [resolve(item, path, missing) for item in value]
        return value

    for time, raw, path, number in rows:
        if time >= until or not raw.get("repo") or raw.get("issue") is None:
            continue
        key = (raw["repo"], raw["issue"])
        if raw.get("node") != "check" and key not in pending:
            continue
        missing = []
        row = resolve(raw, path, missing)
        before, after, event = (row.get(name, {}) for name in ("before", "after", "event"))
        fields = event.get("fields", {})
        start = row.get("kind") == "transition" and fields.get("local_ci", False) is None and fields.get("tested") is False
        completed = (row.get("kind") == "transition" and before.get("node") == "check"
                     and (after.get("check_rounds", 0) > before.get("check_rounds", 0)
                          or event.get("action") == "verdict" and event.get("outcome", {}).get("result") in ("fix", "merge")))
        if key not in pending and not (start or completed or row.get("call") == "decide"
                                      and row.get("name") != "shadow"):
            continue
        if key not in pending and completed and (key, after.get("check_rounds"), after.get("sha")) in finished:
            continue
        if start and key in pending:
            previous = pending.pop(key)
            if since <= timestamp(previous["start"]) < until:
                rounds.append({**previous, "end": None, "sha": None, "round": None, "a": None})
        if key not in pending:
            if raw.get("node") != "check":
                continue
            pending[key] = {"repo": key[0], "issue": key[1], "start": row["ts"],
                            "boundary": start, "records": [], "missing": []}
        current = pending[key]
        current["missing"].extend(missing)
        current["records"].append({"source": str(path), "line": number, "record": row})
        if not completed:
            continue
        current.update(end=row["ts"], sha=after.get("sha") or before.get("sha"),
                       round=after.get("check_rounds"),
                       a=fields.get("last_check") or fields.get("verdict") or event.get("outcome"))
        identity = (key, current["round"], current["sha"])
        if since <= time and (current["round"] is None or identity not in finished):
            rounds.append(current)
        finished.add(identity)
        del pending[key]
    rounds.extend({**current, "end": None, "sha": None, "round": None, "a": None}
                  for current in pending.values() if since <= timestamp(current["start"]) < until)
    for current in rounds:
        current["id"] = digest({key: current[key] for key in ("repo", "issue", "start", "round", "sha")})
        gaps = set(current.pop("missing"))
        if not current["boundary"]:
            gaps.add("start_boundary")
        if not current["end"]:
            gaps.add("unfinished_round")
        if not current["sha"]:
            gaps.add("reviewed_revision")
        if not current["a"]:
            gaps.add("original_a_result")
        inputs = []
        for item in current["records"]:
            row = item["record"]
            effect = row.get("effect", {})
            internal = effect.get("input", {})
            if row.get("call") != "decide" or row.get("name") == "shadow" or not isinstance(internal, dict):
                continue
            state = internal.get("state", {})
            if state.get("sha") != current["sha"]:
                gaps.add("decision_revision")
            if not internal.get("questions") or "output" not in effect or row.get("ok") is not True:
                gaps.add("decision_input_or_result")
            for name in ("diff_path", "test_log_path"):
                if state.get(name):
                    gaps.add("unresolved_file:" + state[name])
            inputs.append({"source": item["source"], "line": item["line"], "effect": effect})
        if not inputs:
            gaps.add("review_inputs")
        current["inputs"] = inputs
        current["review_gaps"] = sorted(gaps)
        current["findings"] = []
        for index, finding in enumerate((current["a"] or {}).get("uwagi", [])):
            entry = {"id": digest([current["id"], index, finding]), "round": current["id"],
                     "sha": current["sha"], "ts": current["end"] or current["start"], "finding": finding}
            current["findings"].append({**entry, **classify(entry, evidence)})
    rounds.sort(key=lambda row: (row["start"], row["id"]))
    if len({row["id"] for row in rounds}) != len(rounds):
        raise ValueError("duplicate Check round")
    findings = [finding for row in rounds for finding in row["findings"]]
    payload = {"version": 1, "since": since.isoformat(), "until_exclusive": until.isoformat(),
               "sources": sources, "outcome_evidence": evidence, "rounds": rounds,
               "validation": {"expected": expected, "count": len(rounds), "membership_complete": len(rounds) == expected and all(row["boundary"] and row["end"] for row in rounds),
                              "review_complete": all(not row["review_gaps"] for row in rounds) and bool(rounds),
                              "labels_complete": bool(rounds) and all(row["a"] is not None for row in rounds)
                              and all(row["label"] not in ("incomplete", "ambiguous") for row in findings)}}
    return {**payload, "sha256": digest(payload)}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="lokay dataset")
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--since", required=True, type=timestamp)
    parser.add_argument("--until", required=True, type=timestamp)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--expected", type=int, default=139)
    args = parser.parse_args(argv)
    try:
        if args.expected < 1:
            raise ValueError("expected count must be positive")
        evidence = json.loads(args.evidence.read_text()) if args.evidence else []
        if not isinstance(evidence, list) or any(not isinstance(row, dict) for row in evidence):
            raise ValueError("expected an outcome evidence array")
        payload = corpus(args.source, args.since, args.until, evidence, args.expected)
        store.freeze_dataset(args.output, payload)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"dataset: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"output": str(args.output), "sha256": payload["sha256"], **payload["validation"]}, sort_keys=True))
    return 0 if all(payload["validation"][key] for key in ("membership_complete", "review_complete", "labels_complete")) else 1
