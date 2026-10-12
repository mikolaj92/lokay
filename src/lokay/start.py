from __future__ import annotations

import json
import os
import shutil
import time
from functools import wraps
from pathlib import Path

from lokay.config import load_repos
from lokay.gh import _gh, gh_bin, open_issues, open_pr_for
from lokay.lock import acquire, release
from lokay.run import run_process
from lokay.state import rounds_append, run_dir, state_read, state_update


def guarded_step(step):
    @wraps(step)
    def guarded(picked: dict) -> dict:
        current_step = step
        while True:
            try:
                outcome = current_step(picked)
            except Exception as exc:
                outcome = {"result": "failed", "reason": f"{type(exc).__name__}: {exc}"}
            repo, issue = picked["repo"], picked["issue"]
            if outcome.get("result") == "merged":
                state_update(repo, issue, failures=0, retry_at=0, reason=None)
                return outcome
            state = state_read(repo, issue)
            failures = state.get("failures", 0) + 1
            reason = outcome.get("reason") or outcome.get("error") or outcome.get("artifact") or "node failed"
            delay = min(3600, 60 * 2 ** min(failures - 1, 6))
            state_update(repo, issue, result="failed", reason=reason, failures=failures,
                         retry_at=time.time() + delay)
            rounds_append(repo, issue, f"{state.get('node', picked['node'])}: retry, reason={reason}")
            time.sleep(delay)
            picked = {**picked, "node": state.get("node", picked["node"])}
            current_step = advance.__wrapped__ if picked["node"] in ("plan", "build") else resume.__wrapped__
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
        args = ["/usr/bin/curl", "-sS", "-m", "5", "-o", "/dev/null", "-w", "%{http_code}"]
        if child.get("LOKAY2_DECISION_API_KEY"):
            args.extend(["-H", f"authorization: Bearer {child['LOKAY2_DECISION_API_KEY']}"])
        args.append(url)
        try:
            fetched = run_process(
                args,
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
    repos = [repo for repo in load_repos(Path(repos_file) if repos_file else None)
             if not only_repo or repo["name"] == only_repo]
    has_open_pr = False
    for repo in repos:
        name = repo["name"]
        code, out, err = _gh([
            "pr", "list", "--repo", name, "--state", "open", "--limit", "1000000",
            "--json", "number,headRefName,headRefOid",
        ])
        if code != 0:
            raise RuntimeError(err.strip() or "pr list failed")
        prs = [row for row in json.loads(out or "[]")
               if row["headRefName"].startswith("lokay/")
               and row["headRefName"][6:].isdecimal()
               and (only_issue is None or int(row["headRefName"][6:]) == only_issue)]
        if not prs:
            continue
        has_open_pr = True
        pr = min(prs, key=lambda row: int(row["number"]))
        issue = int(pr["headRefName"][6:])
        held = acquire(name.split("/")[0], name)
        if held["result"] != "held":
            continue
        try:
            state_update(name, issue, node="check", branch=pr["headRefName"], pr=pr["number"])
        except BaseException:
            release(held)
            raise
        return {"result": "picked", "repo": name, "issue": issue,
                "node": "check", "pr": pr["number"], "held": held}
    if has_open_pr:
        return {"result": "idle", "reason": "no_work"}
    chosen = None
    for repo in repos:
        name = repo["name"]
        owner = name.split("/")[0]
        held = acquire(owner, name)
        if held["result"] != "held":
            continue
        try:
            issues = open_issues(name)
            skipped = load_skips(name)
            issues = [
                row for row in issues
                if int(row["number"]) not in skipped
                and not row["title"].lower().startswith("epic")
                and (only_issue is None or int(row["number"]) == only_issue)
            ]
            issue = next((row for row in issues
                          if state_read(name, row["number"]).get("retry_at", 0) <= time.time()
                          and open_pr_for(name, f"lokay/{row['number']}") is None), None)
            if issue is None:
                continue
            saved = state_read(name, issue["number"])
            branch = f"lokay/{issue['number']}"
            chosen = {
                "result": "picked",
                "repo": name,
                "issue": issue["number"],
                "node": saved.get("node") or "plan",
                "pr": None,
                "held": held,
            }
            state_update(name, issue["number"], node=chosen["node"], branch=branch, pr=chosen["pr"])
        except BaseException:
            release(held)
            raise
        finally:
            if chosen is None:
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
    try:
        print(json.dumps({k: v for k, v in outcome.items() if k != "held"}, separators=(",", ":")))
        if outcome.get("node") in ("plan", "build"):
            print(json.dumps(advance(outcome), separators=(",", ":")))
        elif outcome.get("node") in ("check", "fix", "merge"):
            print(json.dumps(resume(outcome), separators=(",", ":")))
    finally:
        release(outcome["held"])
    return 0


def _retry(picked: dict, node: str, action, expected: str | None = None):
    failures = 0
    while True:
        state_update(picked["repo"], picked["issue"], node=node)
        try:
            outcome = action()
            if expected is None or outcome.get("result") == expected:
                state_update(picked["repo"], picked["issue"], failures=0, retry_at=0, reason=None)
                return outcome
            reason = outcome.get("reason") or outcome.get("error") or str(outcome)
        except Exception as exc:
            reason = f"{type(exc).__name__}: {exc}"
        failures += 1
        delay = min(3600, 60 * 2 ** min(failures - 1, 6))
        state_update(picked["repo"], picked["issue"], failures=failures,
                     reason=reason, retry_at=time.time() + delay)
        rounds_append(picked["repo"], picked["issue"], f"{node}: retry, reason={reason}")
        time.sleep(delay)


@guarded_step
def advance(picked: dict) -> dict:
    worktree, branch, sha, tests, plan_rounds = _prepare(picked)
    return _finish(picked, worktree, branch, sha, tests, plan_rounds)


def _prepare(picked: dict) -> tuple:
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
    saved = state_read(picked["repo"], picked["issue"])
    plan_rounds = saved.get("plan_rounds", 0)
    if saved.get("node", picked["node"]) == "plan" or saved.get("plan_phase") or not plan.valid_plan(art):
        art.parent.mkdir(parents=True, exist_ok=True)
        original_prompt = plan.prompt_for(title, body)
        prompt = saved.get("plan_prompt") or original_prompt
        phase = saved.get("plan_phase") or ("check" if plan.valid_plan(art) else "write")
        while True:
            if phase == "write" or not plan.valid_plan(art):
                state_update(picked["repo"], picked["issue"], plan_phase="write", plan_prompt=prompt)
                def write_plan():
                    written = plan.plan_write(prompt, art)
                    if written["result"] == "done" and not plan.valid_plan(art):
                        return {"result": "failed", "reason": "invalid plan"}
                    return written
                _retry(picked, "plan", write_plan, "done")
                plan_rounds += 1
            state_update(picked["repo"], picked["issue"], plan_phase="check", plan_rounds=plan_rounds)
            plan_text = art.read_text()
            answers = _retry(picked, "plan", lambda: decide(plan.plan_questions(plan_text)))
            verdict = plan.verdict(answers)
            state_update(picked["repo"], picked["issue"], node="plan", plan_rounds=plan_rounds, result=verdict["next"])
            rounds_append(picked["repo"], picked["issue"], f"Plan {plan_rounds}: {verdict['next']}")
            if verdict["next"] == "ok":
                state_update(picked["repo"], picked["issue"], node="build", plan_phase=None, plan_prompt=None)
                break
            uwagi = ", ".join(row["kryterium"] for row in verdict["uwagi"])
            prompt = original_prompt + f"\nUwagi: {uwagi or 'revise the plan'}.\n"
            phase = "write"
            state_update(picked["repo"], picked["issue"], plan_phase=phase, plan_prompt=prompt)
    repo = next(row for row in load_repos() if row["name"] == picked["repo"])
    root = Path(os.path.expanduser(repo["clone_path"]))
    worktree = root.parent / f"{root.name}-wt-{picked['issue']}"
    branch = f"lokay/{picked['issue']}"
    if not worktree.exists():
        _retry(picked, "build", lambda: worktree_add(root, branch, worktree), "added")
    plan_text = art.read_text()
    state_update(picked["repo"], picked["issue"], node="build", branch=branch)
    _retry(picked, "build", lambda: build_code(
        worktree, plan_text, title, body, dict(os.environ), expected_branch=branch,
    ), "done")
    def publish():
        pr = open_pr_for(picked["repo"], branch)
        expected = pr.get("headRefOid") if pr else None
        outcome = build_publish(
            worktree, branch, expected, picked["repo"], int(picked["issue"]),
            title, f"Closes #{picked['issue']}\n\n" + plan_text[:6000],
        )
        if outcome.get("result") == "pr_open" and not outcome.get("sha"):
            return {"result": "failed", "reason": "missing published SHA"}
        return outcome
    published = _retry(picked, "build", publish, "pr_open")
    state_update(
        picked["repo"], picked["issue"], pr=published.get("pr"),
        sha=published.get("sha"), result=published["result"],
    )
    state_update(picked["repo"], picked["issue"], node="check", verdict=None, fix_fingerprint=None)
    return worktree, branch, published["sha"], repo.get("test") or [], plan_rounds


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
            def restore():
                code, out, err = _git(root, args)
                if code != 0 and args[0] == "worktree" and "already exists" in (err + out):
                    code, out, err = _git(root, ["worktree", "add", str(worktree), branch])
                return {"result": "done" if code == 0 else "failed", "error": err.strip() or out.strip()}
            _retry(picked, picked["node"], restore, "done")
    pr = _retry(picked, picked["node"], lambda: open_pr_for(picked["repo"], branch))
    if pr is None or not pr.get("headRefOid"):
        return advance({**picked, "node": "build"})
    state_update(picked["repo"], picked["issue"], pr=pr["number"], sha=pr["headRefOid"])
    return _finish(picked, worktree, branch, pr["headRefOid"], repo.get("test") or [])


def _finish(picked: dict, worktree: Path, branch: str, sha: str, tests: list, plan_rounds: int = 1) -> dict:
    from lokay.check import aggregate, decide_hunks, hunks, questions
    from lokay.decide import decide
    from lokay.fix import fix_code, fix_publish
    from lokay import plan
    from lokay.git import _git
    from lokay.gh import _gh, open_pr_for
    from lokay.merge import merge_sha
    from lokay.run import run_process

    saved = state_read(picked["repo"], picked["issue"])
    rounds = saved.get("check_rounds", 0)
    verdict = saved.get("verdict")
    pending = "check" if saved.get("node") == "merge" else saved.get("node")

    def sync_head():
        for args in (["fetch", "origin", branch], ["merge", "--ff-only", f"origin/{branch}"]):
            code, out, err = _git(worktree, args)
            if code != 0:
                raise RuntimeError(err or out)

    def sync_main():
        code, out, err = _git(worktree, ["fetch", "origin", "main"])
        if code != 0:
            raise RuntimeError(err or out)
        code, out, err = _git(worktree, ["diff", "--name-only", "--diff-filter=U"])
        if code != 0:
            raise RuntimeError(err or out)
        if out.strip():
            return out.splitlines()
        code, out, err = _git(worktree, ["merge", "--no-edit", "--no-ff", "origin/main"])
        if code != 0:
            conflict_code, files, conflict_err = _git(worktree, ["diff", "--name-only", "--diff-filter=U"])
            if conflict_code == 0 and files.strip():
                return files.splitlines()
            raise RuntimeError(conflict_err or err or out)
        return []

    while True:
        if pending == "merge" and verdict and verdict.get("sha") == sha:
            pr = _retry(picked, "merge", lambda: open_pr_for(picked["repo"], branch))
            if pr and pr.get("headRefOid") == sha:
                state_update(picked["repo"], picked["issue"], node="merge", pr=pr["number"])
                merged = _retry(picked, "merge", lambda: merge_sha(
                    picked["repo"], pr["number"], sha, verdict, worktree,
                    picked.get("held"), picked["repo"].split("/")[0], int(picked["issue"]),
                    {"plan_rounds": plan_rounds, "check_rounds": rounds},
                ))
                state_update(picked["repo"], picked["issue"], result=merged["result"])
                if merged["result"] == "merged":
                    state_update(picked["repo"], picked["issue"], sha=merged["merge_sha"])
                    rounds_append(picked["repo"], picked["issue"], f"Merge: sha={merged['merge_sha']}")
                    return merged
                rounds_append(picked["repo"], picked["issue"], f"Merge: retry, result={merged['result']}")
                if merged["result"] != "conflict":
                    time.sleep(60)
            if pr and pr.get("headRefOid") and pr["headRefOid"] != sha:
                _retry(picked, "check", sync_head)
                sha = pr["headRefOid"]
            pending = "check"
        state_update(picked["repo"], picked["issue"], node="fix" if pending == "fix" else "check", sha=sha)
        if pending != "fix":
            conflicts = _retry(picked, "check", sync_main)
            if conflicts:
                verdict = {"result": "fix", "sha": sha, "uwagi": [
                    {"pytanie": "conflict", "plik": file, "log": "Resolve the merge with origin/main."}
                    for file in conflicts
                ]}
                pending = "fix"
                state_update(picked["repo"], picked["issue"], node="fix", verdict=verdict)
                rounds_append(picked["repo"], picked["issue"], "Check: conflict, files=" + ", ".join(conflicts))
            else:
                pushed = _retry(picked, "check", lambda: fix_publish(worktree, branch, sha))
                if pushed["result"] == "remote_moved" and pushed.get("sha"):
                    _retry(picked, "check", sync_head)
                    sha = pushed["sha"]
                    pending = "check"
                    continue
                if pushed["result"] != "pushed":
                    raise RuntimeError(f"main synchronization publish failed: {pushed}")
                sha = pushed["sha"]
                state_update(picked["repo"], picked["issue"], sha=sha, verdict=None)
        def read_diff():
            diff = run_process(["git", "diff", "origin/main...HEAD"], cwd=worktree, timeout=30)
            if diff.returncode != 0:
                raise RuntimeError(diff.stderr or "diff failed")
            return diff
        diff = _retry(picked, "check", read_diff)
        if pending == "fix" and verdict:
            uwagi = verdict["uwagi"]
            fingerprint = json.dumps(sorted(json.dumps(row, sort_keys=True) for row in uwagi))
            saved = state_read(picked["repo"], picked["issue"])
            replan = saved.get("fix_fingerprint") == fingerprint
            if not replan:
                state_update(picked["repo"], picked["issue"], fix_fingerprint=fingerprint)
                prompt = (
                    Path(__file__).resolve().parents[2].joinpath("prompts/fix.md").read_text()
                    + "\n\nUwagi:\n" + json.dumps(uwagi)
                    + "\n\nDiff:\n" + (diff.stdout or "")[:20000]
                    + "\n\nPrevious failure:\n" + (saved.get("fix_reason") or "")
                )
                try:
                    fixed = fix_code(worktree, sha, prompt, dict(os.environ))
                except Exception as exc:
                    fixed = {"result": "failed", "reason": str(exc)}
                replan = fixed.get("reason") == "no_changes"
                if fixed["result"] != "done" and not replan:
                    state_update(picked["repo"], picked["issue"], fix_reason=str(fixed))
                    time.sleep(60)
                    continue
            if replan:
                code, raw, _err = _retry(picked, "plan", lambda: _gh(
                    ["issue", "view", str(picked["issue"]), "--repo", picked["repo"], "--json", "title,body"]
                ))
                issue = json.loads(raw) if code == 0 and raw.strip() else {}
                prompt = plan.prompt_for(issue.get("title") or f"issue {picked['issue']}", issue.get("body"))
                prompt += "\n\nUwagi:\n" + json.dumps(uwagi) + "\nFix made no progress; revise the plan.\n"
                state_update(picked["repo"], picked["issue"], node="plan", plan_phase="write", plan_prompt=prompt)
                worktree, branch, sha, tests, plan_rounds = _prepare({**picked, "node": "plan"})
            else:
                pushed = _retry(picked, "fix", lambda: fix_publish(worktree, branch, sha))
                if pushed["result"] == "remote_moved" and pushed.get("sha"):
                    _retry(picked, "check", sync_head)
                    sha = pushed["sha"]
                elif pushed["result"] != "pushed":
                    state_update(picked["repo"], picked["issue"], fix_reason=str(pushed))
                    time.sleep(60)
                    continue
                else:
                    sha = pushed["sha"]
                state_update(picked["repo"], picked["issue"], sha=sha, fix_reason=None)
                rounds_append(picked["repo"], picked["issue"], f"Fix: sha={sha}")
            pending = "check"
            continue
        rows = hunks(diff.stdout or "")
        failed = []
        if tests:
            proc = _retry(picked, "check", lambda: run_process(tests, cwd=worktree, timeout=600))
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
            answers = _retry(picked, "check", lambda: decide({"state": {"sha": sha, "kind": kind}, "questions": questions(kind, rows)["questions"]}))
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
        pending = verdict["result"]
        state_update(picked["repo"], picked["issue"], node=pending)
