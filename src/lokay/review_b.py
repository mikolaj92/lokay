from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

from lokay import store
from lokay.dataset import digest
from lokay.effects.decide import DecisionError, from_wire, to_wire
from lokay.effects.review_b import invoke
from lokay.review import THRESHOLD
from lokay.types import Finding, parse_finding, to_dict


def verified(payload: dict) -> dict:
    if payload.get("sha256") != digest({key: value for key, value in payload.items() if key != "sha256"}):
        raise ValueError("artifact hash mismatch")
    return payload


def sealed(payload: dict) -> dict:
    return {**payload, "sha256": digest(payload)}


def approval(payload: dict) -> dict:
    verified(payload)
    endpoint = urlsplit(payload["endpoint"])
    if (payload.get("task") != 0 or payload.get("decision") != "approved"
            or not payload.get("source") or not payload.get("evidence") or not payload.get("model")
            or endpoint.scheme != "http" or endpoint.hostname not in ("127.0.0.1", "::1")
            or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment
            or not endpoint.path.endswith("/chat/completions")):
        raise ValueError("task 0 approval evidence and a loopback chat endpoint required")
    return payload


def request(round: dict) -> tuple[dict, dict]:
    questions = []
    states = {}
    locations = {}
    for index, item in enumerate(round["inputs"]):
        internal = item["effect"]["input"]
        prefix = f"r{index}_"
        states[prefix] = internal["state"]
        for question in internal["questions"]:
            qid = prefix + question["id"]
            questions.append({**question, "id": qid,
                              "instructions": f"Use state {prefix}. " + question["instructions"]})
            if question["id"].startswith("h"):
                match = re.search(r"([^\s]+):(\d+)-(\d+)$", question["instructions"])
                if match:
                    path, start, end = match.groups()
                    locations[qid] = to_dict(Finding(path, int(start), int(end), rule_id="diff_paths"))
    if not questions or len({item["id"] for item in questions}) != len(questions):
        raise ValueError("missing or duplicate review questions")
    return {"state": states, "questions": questions}, locations


def wire(round: dict, model: str) -> dict:
    internal, _ = request(round)
    body = to_wire("chat", model, internal)
    expected = {**internal, "questions": [{key: item[key] for key in ("id", "instructions", "options")}
                                           for item in internal["questions"]]}
    if json.loads(body["messages"][1]["content"]) != expected:
        raise ValueError("single chat would truncate frozen inputs")
    return body


def decode(round: dict, model: str, call: dict) -> dict:
    internal, locations = request(round)
    result = {"json_valid": False, "decision_valid": False, "result": None}
    if call.get("error") or call.get("status") != 200:
        return result
    try:
        payload = json.loads(call["raw"])
        json.loads(payload["choices"][0]["message"]["content"])
        result["json_valid"] = True
        answers = from_wire("chat", model, payload, internal)
        findings = []
        for qid, location in locations.items():
            answer = answers[qid]
            if answer["probabilities"].get("true", 0) >= THRESHOLD:
                findings.append({**location, "p": answer["probabilities"]["true"],
                                 "uzasadnienie": answer.get("reason", "")})
        problem = bool(findings) or any(answer["choice"] == "issue" for answer in answers.values())
        result.update(decision_valid=True, result={"next": "issue" if problem else "ok", "uwagi": findings})
    except (ValueError, KeyError, IndexError, TypeError, AttributeError, DecisionError):
        pass
    return result


def same_location(left: dict, right: dict) -> bool:
    a, b = parse_finding(left), parse_finding(right)
    return (isinstance(a, Finding) and isinstance(b, Finding)
            and (a.plik, a.linia_od, a.linia_do) == (b.plik, b.linia_od, b.linia_do))


def report(corpus: dict, recording: dict) -> dict:
    verified(corpus)
    verified(recording)
    model = approval(recording["approval"])["model"]
    rounds = corpus["rounds"]
    if len({row["id"] for row in rounds}) != len(rounds):
        raise ValueError("duplicate frozen round")
    if recording["corpus"] != corpus["sha256"] or len(recording["rounds"]) != len(rounds):
        raise ValueError("recording does not match frozen corpus")
    details = []
    a_caught = b_caught = a_escapes = b_escapes = missed = eligible = 0
    a_seconds = b_seconds = 0.0
    a_calls = 0
    a_timing_complete = True
    for round, saved in zip(rounds, recording["rounds"]):
        if saved["id"] != round["id"] or saved["sha"] != round["sha"]:
            raise ValueError("recorded round identity mismatch")
        call = saved["call"]
        if call["body"] != wire(round, model):
            raise ValueError("recorded request mismatch")
        seconds = call["seconds"]
        if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0:
            raise ValueError("invalid call duration")
        b_seconds += seconds
        decoded = decode(round, model, call)
        detected = (decoded["result"] or {}).get("uwagi", [])
        for finding in round["findings"]:
            if finding["label"] not in ("true_error", "escape"):
                continue
            eligible += 1
            caught_a = finding["label"] == "true_error"
            caught_b = any(same_location(finding["finding"], item) for item in detected)
            a_caught += caught_a
            b_caught += caught_b
            a_escapes += not caught_a
            b_escapes += not caught_b
            missed += caught_a and not caught_b
        for item in round["inputs"]:
            a_calls += len(item["effect"].get("requests", []))
        for item in round["records"]:
            row = item["record"]
            if row.get("call") == "decide":
                duration = row.get("ms")
                if type(duration) in (int, float) and math.isfinite(duration) and duration >= 0:
                    a_seconds += duration / 1000
                else:
                    a_timing_complete = False
        details.append({"id": round["id"], "sha": round["sha"], **decoded})
    count = len(rounds)
    valid = sum(row["json_valid"] for row in details)
    relative = b_caught / a_caught if a_caught else None
    json_rate = valid / count if count else None
    complete = (bool(count) and all(not row["review_gaps"] for row in rounds)
                and all(finding["label"] not in ("incomplete", "ambiguous")
                        for row in rounds for finding in row["findings"]))
    complete = complete and all(corpus["validation"].get(key) is True for key in
                                  ("membership_complete", "review_complete", "labels_complete"))
    kills = {"a_caught_b_missed": missed > 0,
             "recall_below_0_8": relative is not None and relative < 0.8,
             "bad_json_above_2_percent": bool(count) and (count - valid) / count > 0.02}
    acceptance = {"recall_at_least_0_9": relative is not None and relative >= 0.9,
                  "no_more_escapes": b_escapes <= a_escapes,
                  "json_at_least_99_percent": json_rate is not None and json_rate >= 0.99}
    accepted = (complete and all(row["decision_valid"] for row in details)
                and all(acceptance.values()) and not any(kills.values()))
    return {"corpus": corpus["sha256"], "recording": recording["sha256"], "rounds": count,
            "eligible_errors": eligible, "a_caught": a_caught, "b_caught": b_caught,
            "a_recall": a_caught / eligible if eligible else None,
            "b_recall": b_caught / eligible if eligible else None, "relative_recall": relative,
            "a_escapes": a_escapes, "b_escapes": b_escapes, "a_caught_b_missed": missed,
            "json_valid": valid, "json_denominator": count, "json_rate": json_rate,
            "a_calls": a_calls, "b_calls": count,
            "a_seconds": a_seconds if a_timing_complete else None, "b_seconds": b_seconds,
            "finding_match": "exact path and line range", "evidence_complete": complete,
            "acceptance": acceptance, "kill": kills,
            "shadow_eligible": accepted, "details": details}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="lokay review-b")
    parser.add_argument("mode", choices=("record", "replay"))
    parser.add_argument("corpus", type=Path)
    parser.add_argument("recording", type=Path)
    parser.add_argument("--approval", type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=180)
    args = parser.parse_args(argv)
    try:
        corpus = verified(json.loads(args.corpus.read_text()))
        if args.mode == "record":
            if args.recording.exists() or args.report.exists():
                raise ValueError("output already exists")
            if args.approval is None or not math.isfinite(args.timeout) or args.timeout <= 0:
                raise ValueError("approval and positive finite timeout required")
            approved = approval(json.loads(args.approval.read_text()))
            if not corpus["rounds"] or not all(corpus["validation"].get(key) is True for key in
                                             ("membership_complete", "review_complete", "labels_complete")):
                raise ValueError("complete frozen corpus required")
            bodies = [wire(round, approved["model"]) for round in corpus["rounds"]]
            saved = [{"id": round["id"], "sha": round["sha"],
                      "call": invoke(approved["endpoint"], body, args.timeout)}
                     for round, body in zip(corpus["rounds"], bodies)]
            store.freeze_dataset(args.recording, sealed({"version": 1, "corpus": corpus["sha256"],
                                                         "approval": approved, "rounds": saved}))
        recording = json.loads(args.recording.read_text())
        result = report(corpus, recording)
        store.freeze_dataset(args.report, sealed(result))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"review-b: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0 if result["shadow_eligible"] else 1
