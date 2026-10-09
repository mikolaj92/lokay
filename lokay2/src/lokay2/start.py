from __future__ import annotations

import os
import shutil
from pathlib import Path

from lokay2.config import load_repos
from lokay2.gh import issues_with_label, open_pr_for
from lokay2.lock import acquire, release
from lokay2.run import run_process


def probes(env: dict[str, str] | None = None) -> dict[str, str]:
    child = dict(os.environ if env is None else env)
    out: dict[str, str] = {}
    if child.get("LOKAY2_GB10") == "down":
        out["gb10"] = "fail"
    else:
        url = (child.get("LOKAY2_DECISION_BASE_URL") or "http://192.168.1.60:8888").rstrip("/") + "/v1/models"
        try:
            fetched = run_process(["curl", "-sS", "-m", "5", "-o", "/dev/null", "-w", "%{http_code}", url], env=child, timeout=8)
            out["gb10"] = "ok" if (fetched.stdout or "").strip() == "200" else "fail"
        except (FileNotFoundError, OSError):
            out["gb10"] = "fail"
    out["provider"] = "ok" if child.get("LOKAY2_PROVIDER") and child.get("LOKAY2_PROVIDER") != child.get("PI_PROVIDER", "") else "fail"
    if child.get("LOKAY2_PROVIDER") and "PI_PROVIDER" not in child:
        out["provider"] = "ok"
    out["model"] = "ok" if child.get("LOKAY2_MODEL") else "fail"
    out["decision"] = "ok" if child.get("LOKAY2_DECISION_API") and child.get("LOKAY2_DECISION_MODEL") else "fail"
    out["pi"] = "ok" if shutil.which("pi", path=child.get("PATH")) else "fail"
    try:
        gh = run_process(["gh", "auth", "status"], env=child, timeout=15)
        out["gh"] = "ok" if gh.returncode == 0 else "fail"
    except FileNotFoundError:
        out["gh"] = "fail"
    return out


def host_ready(report: dict[str, str]) -> bool:
    return all(value == "ok" for value in report.values())


def pick(env: dict[str, str] | None = None) -> dict:
    report = probes(env)
    if not host_ready(report):
        return {"result": "idle", "reason": "host"}
    chosen = None
    for repo in load_repos():
        name = repo["name"]
        owner = name.split("/")[0]
        held = acquire(owner, name)
        if held["result"] != "held":
            continue
        try:
            issues = issues_with_label(name)
        except Exception:
            release(held)
            raise
        if not issues:
            release(held)
            continue
        issue = issues[0]
        branch = f"lokay/{issue['number']}"
        pr = open_pr_for(name, branch)
        chosen = {
            "result": "picked",
            "repo": name,
            "issue": issue["number"],
            "node": "check" if pr else "plan",
            "pr": None if pr is None else pr.get("number"),
        }
        release(held)
        break
    if chosen is None:
        return {"result": "idle", "reason": "no_work"}
    return chosen


def main(argv: list[str] | None = None) -> int:
    import json
    import sys

    args = argv if argv is not None else sys.argv[1:]
    if "--check" in args:
        report = probes()
        print(json.dumps(report, separators=(",", ":")))
        return 0 if host_ready(report) else 1
    outcome = pick()
    if outcome["result"] == "idle":
        print(f"idle {outcome['reason']}", file=sys.stderr)
        return 0
    print(json.dumps(outcome, separators=(",", ":")))
    return 0
