from __future__ import annotations

import json
import os
import shutil
import time
from functools import wraps
from pathlib import Path

from lokay.config import load_repos
from lokay.gh import gh_bin, open_issues, open_pr_for
from lokay.lock import acquire, release
from lokay.run import run_process
from lokay.state import rounds_append, run_dir, state_read, state_update


def guarded_step(step):
    @wraps(step)
    def guarded(picked: dict) -> dict:
        try:
            outcome = step(picked)
        except Exception as exc:
            outcome = {"result": "failed", "reason": f"{type(exc).__name__}: {exc}"}
        repo, issue = picked["repo"], picked["issue"]
        if outcome.get("result") == "failed":
            state = state_read(repo, issue)
            failures = state.get("failures", 0) + 1
            reason = outcome.get("reason") or outcome.get("error") or outcome.get("artifact") or "node failed"
            outcome["reason"] = reason
            state_update(repo, issue, result="failed", reason=reason, failures=failures,
                         retry_at=time.time() + min(3600, 60 * 2 ** min(failures - 1, 6)))
            rounds_append(repo, issue, f"{state.get('node', picked['node'])}: failed, reason={reason}")
        else:
            state_update(repo, issue, failures=0, retry_at=0, reason=None)
        return outcome
    return guarded


def skip_file() -> Path:
    return Path.home() / ".lokay" / "skip-issues.json"


def load_skips(repo: str) -> set[int]:
    path = skip_file()
    if not path.is_file():
        return set()
    try:
        data = json.loads(path.read_text() or "{}")
    except json.JSONDecodeError:
        return set()
    rows = data.get(repo) if isinstance(data, dict) else None
    if not isinstance(rows, dict):
        return set()
    found: set[int] = set()
    for key in rows:
        try:
            found.add(int(key))
        except (TypeError, ValueError):
            continue
    return found


def remember_skip(repo: str, issue: int, explanation: str) -> None:
    path = skip_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict = {}
    if path.is_file():
        try:
            loaded = json.loads(path.read_text() or "{}")
        except json.JSONDecodeError:
            loaded = {}
        if isinstance(loaded, dict):
            data = loaded
    bucket = data.get(repo)
    if not isinstance(bucket, dict):
        bucket = {}
    bucket[str(issue)] = explanation
    data[repo] = bucket
    path.write_text(json.dumps(data))



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
        except Exception:
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
    except Exception:
        out["gh"] = "fail"
    return out


def host_ready(report: dict[str, str]) -> bool:
    return all(value == "ok" for value in report.values())


def pick(env: dict[str, str] | None = None) -> dict:
    report = probes(env)
    if not host_ready(report):
        failed = " ".join(f"{name}={value}" for name, value in report.items() if value != "ok")
        return {"result": "idle", "reason": "host", "failed": failed}
    child = os.environ if env is None else env
    repos_file = child.get("LOKAY2_REPOS_FILE")
    only_repo = child.get("LOKAY2_REPO")
    only_issue = int(child["LOKAY2_ISSUE"]) if child.get("LOKAY2_ISSUE") else None
    chosen = None
    for repo in load_repos(Path(repos_file) if repos_file else None):
        name = repo["name"]
        if only_repo and name != only_repo:
            continue
        owner = name.split("/")[0]
        held = acquire(owner, name)
        if held["result"] != "held":
            continue
        try:
            issues = open_issues(name)
        except Exception:
            release(held)
            raise
        skipped = load_skips(name)
        issues = [
            row for row in issues
            if int(row["number"]) not in skipped
            and not row["title"].lower().startswith("epic")
            and (only_issue is None or int(row["number"]) == only_issue)
        ]
        if not issues:
            release(held)
            continue
        issue = next((row for row in issues
                      if state_read(name, row["number"]).get("retry_at", 0) <= time.time()), None)
        if issue is None:
            release(held)
            continue
        saved = state_read(name, issue["number"])
        branch = f"lokay/{issue['number']}"
        try:
            pr = open_pr_for(name, branch)
        finally:
            release(held)
        chosen = {
            "result": "picked",
            "repo": name,
            "issue": issue["number"],
            "node": saved.get("node") or ("check" if pr else "plan"),
            "pr": None if pr is None else pr.get("number"),
        }
        break
    if chosen is None:
        return {"result": "idle", "reason": "no_work"}
    state_update(chosen["repo"], chosen["issue"], node=chosen["node"], branch=branch, pr=chosen["pr"])
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
    if outcome.get("node") in ("plan", "build"):
        print(json.dumps(advance(outcome), separators=(",", ":")))
    elif outcome.get("node") in ("check", "fix", "merge"):
        print(json.dumps(resume(outcome), separators=(",", ":")))
    return 0


@guarded_step
def advance(picked: dict) -> dict:
    from lokay.build import build_code, build_publish
    from lokay.gh import _gh
    from lokay.git import worktree_add

    from lokay import plan
    from lokay.decide import decide

    code, raw, _err = _gh(["issue", "view", str(picked["issue"]), "--repo", picked["repo"], "--json", "title,body"])
    title, body = f"issue {picked['issue']}", None
    if code == 0 and raw.strip():
        loaded = json.loads(raw)
        title = loaded.get("title") or title
        body = loaded.get("body")
    art = run_dir(picked["repo"], picked["issue"]) / "plan.md"
    plan_rounds = 1
    if picked["node"] == "plan" or not plan.valid_plan(art):
        art.parent.mkdir(parents=True, exist_ok=True)
        original_prompt = plan.prompt_for(title, body)
        prompt = original_prompt
        for plan_rounds in range(1, 4):
            written = {"result": "done"} if plan_rounds == 1 and plan.valid_plan(art) else plan.plan_write(prompt, art)
            if written["result"] != "done" or not plan.valid_plan(art):
                state_update(picked["repo"], picked["issue"], node="plan", plan_rounds=plan_rounds, result="failed")
                rounds_append(picked["repo"], picked["issue"], f"Plan {plan_rounds}: failed")
                return {"result": "failed", "artifact": ""}
            plan_text = art.read_text()
            answers = decide(plan.plan_questions(plan_text))
            verdict = plan.verdict(answers)
            state_update(picked["repo"], picked["issue"], node="plan", plan_rounds=plan_rounds, result=verdict["next"])
            rounds_append(picked["repo"], picked["issue"], f"Plan {plan_rounds}: {verdict['next']}")
            if verdict["next"] != "revise":
                break
            uwagi = ", ".join(row["kryterium"] for row in verdict["uwagi"])
            prompt = original_prompt + f"\nUwagi: {uwagi or 'revise the plan'}.\n"
    repo = next(row for row in load_repos() if row["name"] == picked["repo"])
    root = Path(os.path.expanduser(repo["clone_path"]))
    worktree = root.parent / f"{root.name}-wt-{picked['issue']}"
    branch = f"lokay/{picked['issue']}"
    if not worktree.exists():
        added = worktree_add(root, branch, worktree)
        if added["result"] != "added":
            return {"result": "failed", "artifact": ""}
    plan_text = art.read_text()
    state_update(picked["repo"], picked["issue"], node="build", branch=branch)
    built = build_code(
        worktree,
        plan_text,
        title,
        body,
        dict(os.environ),
        expected_branch=branch,
    )
    if built.get("reason") == "outside_worktree":
        remember_skip(picked["repo"], int(picked["issue"]), built.get("explanation") or "outside_worktree")
    if built["result"] != "done":
        return built
    published = build_publish(
        worktree, branch, None, picked["repo"], int(picked["issue"]),
        title, f"Closes #{picked['issue']}\n\n" + plan_text[:6000],
    )
    state_update(
        picked["repo"], picked["issue"], pr=published.get("pr"),
        sha=published.get("sha"), result=published["result"],
    )
    if published.get("result") != "pr_open" or not published.get("sha"):
        return published
    return _finish(picked, worktree, branch, published["sha"], repo.get("test") or [], plan_rounds)


@guarded_step
def resume(picked: dict) -> dict:
    from lokay.git import _git

    repo = next(row for row in load_repos() if row["name"] == picked["repo"])
    root = Path(os.path.expanduser(repo["clone_path"]))
    worktree = root.parent / f"{root.name}-wt-{picked['issue']}"
    branch = f"lokay/{picked['issue']}"
    if not worktree.exists():
        for args in (
            ["fetch", "origin", branch],
            ["worktree", "add", "--track", "-b", branch, str(worktree), f"origin/{branch}"],
        ):
            code, out, err = _git(root, args)
            if code != 0 and args[0] == "worktree" and "already exists" in (err + out):
                code, out, err = _git(root, ["worktree", "add", str(worktree), branch])
            if code != 0:
                return {"result": "failed", "error": err.strip() or out.strip()}
    pr = open_pr_for(picked["repo"], branch)
    if pr is None or not pr.get("headRefOid"):
        return {"result": "failed", "artifact": ""}
    state_update(picked["repo"], picked["issue"], pr=pr["number"], sha=pr["headRefOid"])
    return _finish(picked, worktree, branch, pr["headRefOid"], repo.get("test") or [])


def _finish(picked: dict, worktree: Path, branch: str, sha: str, tests: list, plan_rounds: int = 1) -> dict:
    from lokay.check import aggregate, decide_hunks, hunks, questions
    from lokay.decide import decide
    from lokay.fix import fix_code, fix_publish
    from lokay.gh import open_pr_for
    from lokay.merge import merge_sha
    from lokay.run import run_process

    saved = state_read(picked["repo"], picked["issue"])
    rounds = saved.get("check_rounds", 0)
    verdict = saved.get("verdict")
    pending = saved.get("node")
    while pending != "merge":
        state_update(picked["repo"], picked["issue"], node="fix" if pending == "fix" else "check", sha=sha)
        if pending == "fix":
            break
        diff = run_process(["git", "diff", "origin/main...HEAD"], cwd=worktree, timeout=30)
        rows = hunks(diff.stdout or "")
        failed = []
        if tests:
            proc = run_process(tests, cwd=worktree, timeout=600)
            log = ((proc.stdout or "") + (proc.stderr or ""))[-3000:]
            test_failed = proc.returncode != 0
            if test_failed:
                failed.append({
                    "warstwa": " ".join(tests), "plik": "", "linia": None,
                    "log": log,
                })
        ci = {"result": "red" if failed else "green", "sha": sha, "failed": failed}
        decisions = []
        for kind in ("scope", "tests", "correctness"):
            answers = decide({"state": {"sha": sha, "kind": kind}, "questions": questions(kind, rows)["questions"]})
            wire = {
                "model": os.environ.get("LOKAY2_DECISION_MODEL") or os.environ.get("LOKAY2_MODEL", ""),
                "usage": {"completion_tokens": 0},
                "answers": {qid: {"choice": row["choice"], "probabilities": row["probabilities"]} for qid, row in answers.items()},
            }
            decision = decide_hunks(kind, rows, wire, wire["model"])
            decision["sha"] = sha
            decisions.append(decision)
        verdict = aggregate(sha, ci, decisions)
        rounds += 1
        state_update(
            picked["repo"], picked["issue"], node="check", sha=sha,
            check_rounds=rounds, result=verdict["result"], verdict=verdict,
        )
        counts = ", ".join(
            f"{kind}={len(decision['uwagi'])}"
            for kind, decision in zip(("scope", "tests", "correctness"), decisions)
        )
        rounds_append(
            picked["repo"], picked["issue"],
            f"Check {rounds}: sha={sha}, result={verdict['result']}, uwagi: {counts}, ci={ci['result']}",
        )
        if verdict["result"] == "merge":
            break
        prompt = (
            Path(__file__).resolve().parents[2].joinpath("prompts/fix.md").read_text()
            + "\n\nUwagi:\n" + json.dumps(verdict["uwagi"])
            + "\n\nDiff:\n" + (diff.stdout or "")[:20000]
        )
        state_update(picked["repo"], picked["issue"], node="fix")
        fixed = fix_code(worktree, sha, prompt, dict(os.environ))
        if fixed["result"] != "done":
            return fixed
        pushed = fix_publish(worktree, branch, sha)
        if pushed["result"] != "pushed":
            return pushed
        sha = pushed["sha"]
        state_update(picked["repo"], picked["issue"], sha=sha, result=pushed["result"])
        rounds_append(picked["repo"], picked["issue"], f"Fix: sha={sha}")
    pr = open_pr_for(picked["repo"], branch)
    if pr is None or pr.get("headRefOid") != sha:
        return {"result": "pr_open", "sha": sha}
    state_update(picked["repo"], picked["issue"], node="merge", pr=pr["number"])
    merged = merge_sha(
        picked["repo"],
        pr["number"],
        sha,
        verdict,
        worktree,
        None,
        picked["repo"].split("/")[0],
        int(picked["issue"]),
        {"plan_rounds": plan_rounds, "check_rounds": rounds},
    )
    state_update(
        picked["repo"], picked["issue"], result=merged["result"],
        sha=merged["merge_sha"] if merged["result"] == "merged" else sha,
    )
    if merged["result"] == "merged":
        rounds_append(picked["repo"], picked["issue"], f"Merge: sha={merged['merge_sha']}")
    return merged
