from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from lokay2.build import build_code, build_publish
from lokay2.check import aggregate, decide_hunks, hunks
from lokay2.decide import DecisionError, decide
from lokay2.fix import fix_code, fix_publish
from lokay2.git import worktree_add
from lokay2.merge import merge_sha
from lokay2.plan import plan_questions, plan_write, verdict
from lokay2.run import run_process


def emit(payload: dict) -> int:
    print(json.dumps(payload, separators=(",", ":")))
    return 0


def _req() -> dict:
    return json.load(sys.stdin)


def plan_write_main() -> int:
    req = _req()
    artifact = Path(req["artifact"])
    return emit(plan_write(req["prompt"], artifact, cwd=Path(req["cwd"]) if req.get("cwd") else None))


def plan_check_main() -> int:
    req = _req()
    try:
        answers = decide(req.get("decision") or plan_questions())
    except (DecisionError, KeyError, OSError) as exc:
        print(f"decide: {exc}", file=sys.stderr)
        return 1
    return emit(verdict(answers))


def build_code_main() -> int:
    req = _req()
    worktree = Path(req["worktree"])
    if not worktree.exists():
        added = worktree_add(Path(req["repo"]), req["branch"], worktree)
        if added["result"] != "added":
            return emit({"result": "failed", "artifact": ""})
    return emit(build_code(worktree, req["plan"], req["title"], req.get("body"), dict(os.environ)))


def build_publish_main() -> int:
    req = _req()
    return emit(build_publish(Path(req["worktree"]), req["branch"], req.get("expected"), req["repo_name"], int(req["issue"]), req["title"]))


def check_ci_main() -> int:
    req = _req()
    sha = req["sha"]
    failed = []
    for argv in req.get("test") or []:
        proc = run_process(argv, cwd=req.get("cwd"), timeout=req.get("timeout") or 600)
        if proc.returncode != 0:
            failed.append({"warstwa": " ".join(argv), "plik": "", "linia": None})
    if not req.get("test"):
        failed.append({"warstwa": "no_tests", "plik": "", "linia": None})
    return emit({"result": "red" if failed else "green", "sha": sha, "failed": failed})


def _decision_step(kind: str) -> int:
    req = _req()
    rows = hunks(req["diff"])
    try:
        answers = decide(
            {
                "state": {"sha": req["sha"], "kind": kind},
                "questions": __import__("lokay2.check", fromlist=["questions"]).questions(kind, rows)["questions"],
            }
        )
    except (DecisionError, KeyError, OSError) as exc:
        print(f"decide: {exc}", file=sys.stderr)
        return 1
    wire = {
        "model": os.environ.get("LOKAY2_DECISION_MODEL") or os.environ.get("LOKAY2_MODEL", ""),
        "usage": {"completion_tokens": 0},
        "answers": {
            qid: {"choice": row["choice"], "probabilities": row["probabilities"]}
            for qid, row in answers.items()
        },
    }
    model = wire["model"]
    return emit(decide_hunks(kind, rows, wire, model))


def check_aggregate_main() -> int:
    req = _req()
    try:
        return emit(aggregate(req["sha"], req["ci"], req["decisions"]))
    except DecisionError as exc:
        print(f"aggregate: {exc}", file=sys.stderr)
        return 1


def fix_code_main() -> int:
    req = _req()
    return emit(fix_code(Path(req["worktree"]), req["previous"], req["prompt"], dict(os.environ)))


def fix_publish_main() -> int:
    req = _req()
    return emit(fix_publish(Path(req["worktree"]), req["branch"], req.get("expected")))


def merge_main() -> int:
    req = _req()
    return emit(
        merge_sha(
            req["repo"],
            int(req["pr"]),
            req["sha"],
            req["verdict"],
            Path(req["worktree"]) if req.get("worktree") else None,
            None,
            req["owner"],
            int(req["issue"]),
            req.get("rounds") or {},
        )
    )


COMMANDS = {
    "plan-write": plan_write_main,
    "plan-check": plan_check_main,
    "build-code": build_code_main,
    "build-publish": build_publish_main,
    "check-ci": check_ci_main,
    "check-scope": lambda: _decision_step("scope"),
    "check-tests": lambda: _decision_step("tests"),
    "check-correctness": lambda: _decision_step("correctness"),
    "check-aggregate": check_aggregate_main,
    "fix-code": fix_code_main,
    "fix-publish": fix_publish_main,
    "merge": merge_main,
}
