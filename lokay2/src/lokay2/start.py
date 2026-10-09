from __future__ import annotations

import os
import shutil
from pathlib import Path

from lokay2.config import load_repos
from lokay2.gh import gh_bin, issues_with_label, open_pr_for
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
            fetched = run_process(
                ["/usr/bin/curl", "-sS", "-m", "5", "-o", "/dev/null", "-w", "%{http_code}", url],
                env=child,
                timeout=8,
            )
            code = (fetched.stdout or "").strip()
            out["gb10"] = "ok" if code == "200" else "fail"
        except (FileNotFoundError, OSError):
            out["gb10"] = "fail"
    out["provider"] = "ok" if child.get("LOKAY2_PROVIDER") and child.get("LOKAY2_PROVIDER") != child.get("PI_PROVIDER", "") else "fail"
    if child.get("LOKAY2_PROVIDER") and "PI_PROVIDER" not in child:
        out["provider"] = "ok"
    out["model"] = "ok" if child.get("LOKAY2_MODEL") else "fail"
    out["decision"] = "ok" if child.get("LOKAY2_DECISION_API") and child.get("LOKAY2_DECISION_MODEL") else "fail"
    out["pi"] = "ok" if shutil.which("pi", path=child.get("PATH")) else "fail"
    try:
        gh = run_process([gh_bin(), "auth", "status"], env=child, timeout=15)
        out["gh"] = "ok" if gh.returncode == 0 else "fail"
    except FileNotFoundError:
        out["gh"] = "fail"
    return out


def host_ready(report: dict[str, str]) -> bool:
    return all(value == "ok" for value in report.values())


def pick(env: dict[str, str] | None = None) -> dict:
    report = probes(env)
    if not host_ready(report):
        failed = " ".join(f"{name}={value}" for name, value in report.items() if value != "ok")
        return {"result": "idle", "reason": "host", "failed": failed}
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
        extra = outcome.get("failed") or ""
        print(f"idle {outcome['reason']} {extra}".rstrip(), file=sys.stderr)
        return 0
    print(json.dumps(outcome, separators=(",", ":")))
    if outcome.get("node") == "plan":
        print(json.dumps(advance(outcome), separators=(",", ":")))
    return 0


def advance(picked: dict) -> dict:
    from lokay2.build import build_code, build_publish
    from lokay2.git import worktree_add
    from lokay2.plan import valid_plan

    art = Path.home() / ".lokay2/runs" / f"{picked['repo'].replace('/', '__')}" / str(picked["issue"]) / "plan.md"
    if not valid_plan(art):
        from lokay2.plan import plan_write, prompt_for

        art.parent.mkdir(parents=True, exist_ok=True)
        written = plan_write(prompt_for(f"issue {picked['issue']}", None), art)
        if written["result"] != "done" or not valid_plan(art):
            return {"result": "failed", "artifact": ""}
    repo = next(row for row in load_repos() if row["name"] == picked["repo"])
    root = Path(os.path.expanduser(repo["clone_path"]))
    worktree = root.parent / f"{root.name}-wt-{picked['issue']}"
    branch = f"lokay/{picked['issue']}"
    if not worktree.exists():
        added = worktree_add(root, branch, worktree)
        if added["result"] != "added":
            return {"result": "failed", "artifact": ""}
    built = build_code(worktree, art.read_text(), f"issue {picked['issue']}", None, dict(os.environ))
    if built["result"] != "done":
        return built
    published = build_publish(worktree, branch, None, picked["repo"], int(picked["issue"]), f"feat: issue {picked['issue']}")
    if published.get("result") != "pr_open" or not published.get("sha"):
        return published
    from lokay2.gh import open_pr_for
    from lokay2.merge import merge_sha

    pr = open_pr_for(picked["repo"], branch)
    if pr is None or pr.get("headRefOid") != published["sha"]:
        return published
    return merge_sha(
        picked["repo"],
        pr["number"],
        published["sha"],
        {"result": "merge", "sha": published["sha"]},
        worktree,
        None,
        picked["repo"].split("/")[0],
        int(picked["issue"]),
        {"plan_rounds": 1, "check_rounds": 0},
    )
