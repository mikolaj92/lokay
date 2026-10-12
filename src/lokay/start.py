from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
from functools import wraps
from pathlib import Path

from lokay.config import load_repos
from lokay.gh import _gh, gh_bin, open_issues, open_pr_for
from lokay.lock import acquire, release
from lokay.run import run_process
from lokay.state import rounds_append, run_dir, state_read, state_update


class RetryLater(RuntimeError):
    pass


def guarded_step(step):
    @wraps(step)
    def guarded(picked: dict) -> dict:
        try:
            outcome = step(picked)
        except RetryLater as exc:
            return {"result": "failed", "reason": str(exc)}
        except Exception as exc:
            outcome = {"result": "failed", "reason": f"{type(exc).__name__}: {exc}"}
        if outcome.get("next") in ("plan", "build"):
            return outcome
        repo, issue = picked["repo"], picked["issue"]
        if outcome.get("result") in ("pending", "pr_open"):
            return outcome
        if outcome.get("result") == "merged":
            state_update(repo, issue, failures=0, retry_at=0, reason=None)
            from lokay.observe import current

            current(result="merged", node=None, node_since=None)
            return outcome
        state = state_read(repo, issue)
        if (state.get("result") == "failed" and state.get("reason") == outcome.get("reason")
                and state.get("retry_at", 0) > time.time()):
            return outcome
        failures = state.get("failures", 0) + 1
        reason = outcome.get("reason") or outcome.get("error") or outcome.get("artifact") or "node failed"
        delay = min(3600, 60 * 2 ** min(failures - 1, 6))
        state_update(repo, issue, result="failed", reason=reason, failures=failures,
                     retry_at=time.time() + delay)
        rounds_append(repo, issue, f"{state.get('node', picked['node'])}: retry, reason={reason}")
        return {"result": "failed", "reason": reason}
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


def probes(env: dict[str, str] | None = None) -> dict[str, str]:
    child = dict(os.environ if env is None else env)
    out: dict[str, str] = {}
    if child.get("LOKAY2_GB10") == "down":
        out["decision_host"] = "fail"
    else:
        url = (child.get("LOKAY2_DECISION_BASE_URL") or "http://192.168.1.52:8005").rstrip("/") + "/health"
        args = ["/usr/bin/curl", "-sS", "-m", "5", "-w", "\n%{http_code}"]
        if child.get("LOKAY2_DECISION_API_KEY"):
            args.extend(["-H", f"authorization: Bearer {child['LOKAY2_DECISION_API_KEY']}"])
        args.append(url)
        try:
            fetched = run_process(
                args,
                env=child,
                timeout=8,
            )
            raw, _, code = (fetched.stdout or "").rpartition("\n")
            ready = fetched.returncode == 0 and code.strip() == "200" and json.loads(raw).get("ready") is True
            out["decision_host"] = "ok" if ready else "fail"
        except Exception:
            out["decision_host"] = "fail"
    out["provider"] = "ok" if child.get("LOKAY2_PROVIDER") and child.get("LOKAY2_PROVIDER") != child.get("PI_PROVIDER", "") else "fail"
    if child.get("LOKAY2_PROVIDER") and "PI_PROVIDER" not in child:
        out["provider"] = "ok"
    out["model"] = "ok" if child.get("LOKAY2_MODEL") else "fail"
    api = child.get("LOKAY2_DECISION_API") or "mini"
    out["decision"] = "ok" if api == "mini" or child.get("LOKAY2_DECISION_MODEL") else "fail"
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
    candidates = []
    for repo in repos:
        name = repo["name"]
        code, out, err = _gh([
            "pr", "list", "--repo", name, "--state", "open", "--limit", "1000000",
            "--json", "number,headRefName,headRefOid",
        ])
        if code != 0:
            raise RuntimeError(err.strip() or "pr list failed")
        skipped = load_skips(name)
        prs = [row for row in json.loads(out or "[]")
               if row["headRefName"].startswith("lokay/")
               and row["headRefName"][6:].isdecimal()
               and int(row["headRefName"][6:]) not in skipped
               and state_read(name, int(row["headRefName"][6:])).get("retry_at", 0) <= time.time()
               and (only_issue is None or int(row["headRefName"][6:]) == only_issue)]
        if not prs:
            continue
        candidates.extend((state_read(name, int(pr["headRefName"][6:])).get("last_attempt", 0),
                           int(pr["number"]), name, pr) for pr in prs)
    for _, _, name, pr in sorted(candidates, key=lambda row: row[:3]):
        issue = int(pr["headRefName"][6:])
        held = acquire(name.split("/")[0], name)
        if held["result"] != "held":
            continue
        saved_node = state_read(name, issue).get("node")
        node = saved_node if saved_node in ("plan", "build") else "check"
        try:
            state_update(name, issue, node=node, branch=pr["headRefName"], pr=pr["number"],
                         result="running", reason=None, last_attempt=time.time())
        except BaseException:
            release(held)
            raise
        return {"result": "picked", "repo": name, "issue": issue,
                "node": node, "pr": pr["number"], "held": held}
    if candidates:
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
                and row["title"] != "lokay-stalled"
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
            state_update(name, issue["number"], node=chosen["node"], branch=branch, pr=chosen["pr"],
                         result="running", reason=None, last_attempt=time.time())
        except BaseException:
            chosen = None
            raise
        finally:
            if chosen is None:
                release(held)
        break
    if chosen is None:
        return {"result": "idle", "reason": "no_work"}
    return chosen


def refresh_body(repo: str, issue: int) -> dict:
    from lokay.build import pr_body
    from lokay.gh import pr_set_body

    config = next(row for row in load_repos() if row["name"] == repo)
    root = Path(os.path.expanduser(config["clone_path"]))
    worktree = root.parent / f"{root.name}-wt-{issue}"
    pr = open_pr_for(repo, f"lokay/{issue}")
    if not pr:
        raise RuntimeError(f"open PR missing for {repo} lokay/{issue}")
    return pr_set_body(repo, pr["number"], pr_body(worktree, run_dir(repo, issue) / "plan.md"), issue)


def main(argv: list[str] | None = None) -> int:
    import json
    import sys

    args = argv if argv is not None else sys.argv[1:]
    if args and args[0] == "refresh-body":
        if len(args) != 3 or not args[2].isdigit() or int(args[2]) < 1:
            raise ValueError("usage: lokay refresh-body <repo> <issue>")
        print(json.dumps(refresh_body(args[1], int(args[2])), separators=(",", ":")))
        return 0
    if "--check" in args:
        report = probes()
        print(json.dumps(report, separators=(",", ":")))
        return 0 if host_ready(report) else 1
    outcome = pick()
    if outcome["result"] == "idle":
        from lokay.observe import current

        current(result="idle")
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
    repo, issue = picked["repo"], picked["issue"]
    state_update(repo, issue, node=node)
    try:
        outcome = action()
        if expected is None or outcome.get("result") == expected:
            state_update(repo, issue, failures=0, retry_at=0, reason=None)
            return outcome
        reason = outcome.get("reason") or outcome.get("error") or str(outcome)
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
    failures = state_read(repo, issue).get("failures", 0) + 1
    delay = min(3600, 60 * 2 ** min(failures - 1, 6))
    state_update(repo, issue, result="failed", failures=failures,
                 reason=reason, retry_at=time.time() + delay)
    rounds_append(repo, issue, f"{node}: retry, reason={reason}")
    raise RetryLater(reason)


@guarded_step
def advance(picked: dict) -> dict:
    prepared = _prepare(picked)
    if isinstance(prepared, dict):
        return prepared
    worktree, branch, sha, tests, plan_rounds = prepared
    return _finish(picked, worktree, branch, sha, tests, plan_rounds)


def _prepare(picked: dict) -> tuple | dict:
    from lokay.build import build_code, build_publish
    from lokay.gh import _gh
    from lokay.git import worktree_add

    from lokay import plan
    from lokay.decide import decide

    saved = state_read(picked["repo"], picked["issue"])
    if "issue_title" not in saved or "issue_body" not in saved:
        code, raw, err = _gh(["issue", "view", str(picked["issue"]), "--repo", picked["repo"], "--json", "title,body"])
        if code != 0:
            raise RuntimeError(err.strip() or "issue view failed")
        loaded = json.loads(raw)
        if not isinstance(loaded.get("title"), str) or not loaded["title"].strip():
            raise RuntimeError("issue title is missing or invalid")
        body = loaded.get("body")
        if body is not None and not isinstance(body, str):
            raise RuntimeError("issue body is invalid")
        state_update(picked["repo"], picked["issue"], issue_title=loaded["title"], issue_body=body)
        saved = state_read(picked["repo"], picked["issue"])
    title, body = saved["issue_title"], saved["issue_body"]
    art = run_dir(picked["repo"], picked["issue"]) / "plan.md"
    plan_rounds = saved.get("plan_rounds", 0)
    accepted = (plan.valid_plan(art) and saved.get("plan_accepted_sha") ==
                hashlib.sha256(art.read_bytes()).hexdigest())
    if saved.get("node", picked["node"]) == "plan" or saved.get("plan_phase") or not accepted:
        art.parent.mkdir(parents=True, exist_ok=True)
        original_prompt = saved.get("plan_prompt") or plan.prompt_for(title, body)
        prompt = original_prompt
        phase = saved.get("plan_phase") or ("check" if plan.valid_plan(art) else "write")
        evaluations = saved.get("plan_evaluations", 0) if saved.get("plan_phase") else 0
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
            evaluations += 1
            state_update(picked["repo"], picked["issue"], plan_evaluations=evaluations)
            answers = decide(plan.plan_questions(plan_text))
            verdict = plan.verdict(answers)
            if verdict.get("next") not in ("ok", "revise"):
                raise RuntimeError(f"unknown plan verdict: {verdict.get('next')}")
            state_update(picked["repo"], picked["issue"], node="plan", plan_rounds=plan_rounds, result=verdict["next"])
            rounds_append(picked["repo"], picked["issue"], f"Plan {plan_rounds}: {verdict['next']}")
            if verdict["next"] == "ok":
                state_update(picked["repo"], picked["issue"], node="build", plan_phase=None, plan_prompt=None,
                             plan_accepted_sha=hashlib.sha256(art.read_bytes()).hexdigest())
                break
            uwagi = ", ".join(
                ": ".join(str(row[field]) for field in ("kryterium", "text", "notes") if row.get(field))
                for row in verdict["uwagi"]
            )
            prompt = original_prompt + f"\nUwagi: {uwagi or 'revise the plan'}.\n"
            evaluations = 0
            phase = "write"
            state_update(picked["repo"], picked["issue"], plan_evaluations=0,
                         plan_phase=phase, plan_prompt=prompt)
            time.sleep(20)
    repo = next(row for row in load_repos() if row["name"] == picked["repo"])
    root = Path(os.path.expanduser(repo["clone_path"]))
    worktree = root.parent / f"{root.name}-wt-{picked['issue']}"
    branch = f"lokay/{picked['issue']}"
    if not worktree.exists():
        _retry(picked, "build", lambda: worktree_add(root, branch, worktree), "added")
    plan_text = art.read_text()
    state_update(picked["repo"], picked["issue"], node="build", branch=branch)
    from lokay.setup import prepare_dependencies

    prepare_dependencies(worktree, repo, int(picked["issue"]))
    build_note = state_read(picked["repo"], picked["issue"]).get("build_note")
    built = build_code(worktree, plan_text, title, body, dict(os.environ), expected_branch=branch,
                       clone_path=root, **({"build_note": build_note} if build_note else {}))
    if built.get("result") == "failed":
        reason = built.get("reason") or "build failed"
        explanation = built.get("explanation") or built.get("artifact") or ""
        rounds_append(picked["repo"], picked["issue"], f"Build → Plan: {reason}")
        state_update(picked["repo"], picked["issue"], node="plan", plan_phase="write",
                     plan_evaluations=0, plan_accepted_sha=None,
                     plan_prompt=plan.prompt_for(title, body) + f"\nUwagi (Build): {reason}: {explanation}\n"
                     + "Previous Build made no changes. Make the plan concrete and self-contained so it can be implemented now in this repo; if a dependency is missing, plan to implement the minimal part needed.\n",
                     result="failed", reason=reason,
                     failures=state_read(picked["repo"], picked["issue"]).get("failures", 0) + 1, retry_at=0)
        return {**built, "next": "plan"}
    if built.get("result") != "done":
        raise RuntimeError(f"unexpected Build outcome: {built}")
    state_update(picked["repo"], picked["issue"], failures=0, reason=None, retry_at=0, build_note=None)
    def publish():
        pr = open_pr_for(picked["repo"], branch)
        expected = pr.get("headRefOid") if pr else None
        outcome = build_publish(
            worktree, branch, expected, picked["repo"], int(picked["issue"]),
            title, art,
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


def needs_help(picked: dict, reason: str, sha: str | None = None) -> dict:
    repo, issue = picked["repo"], picked["issue"]
    saved = state_read(repo, issue)
    failures = saved.get("failures", 0) + 1
    delay = min(3600, 60 * 2 ** min(failures - 1, 6))
    fields = {"node": "check"}
    if reason.startswith("fix_code"):
        from lokay.plan import prompt_for

        prompt = saved.get("plan_prompt") or prompt_for(
            saved.get("issue_title") or "", saved.get("issue_body"))
        fields.update(node="plan", plan_phase="write", plan_evaluations=0,
                      plan_accepted_sha=None,
                      plan_prompt=prompt + f"\nUwagi (Fix): {reason}\n"
                      + "Previous Fix made no changes. Revise the plan so it can be implemented now.\n")
    state_update(repo, issue, **fields, result="failed", reason=reason,
                 failures=failures, retry_at=time.time() + delay,
                 pr=saved.get("pr", picked.get("pr")),
                 sha=sha if sha is not None else saved.get("sha"))
    rounds_append(repo, issue, f"{reason} → retry later")
    return {"result": "failed", "reason": reason}


def fix_to_build(picked: dict, worktree: Path) -> dict | None:
    from lokay.git import _git
    from lokay.scope import is_test

    saved = state_read(picked["repo"], picked["issue"])
    ci = saved.get("local_ci") or {}
    if ci.get("result") != "red":
        return None
    log = ci.get("log") or ""
    failed = re.findall(r"^FAILED\s+([^\s:]+)::", log, re.MULTILINE)
    if not failed:
        return None
    code, added, err = _git(worktree, ["diff", "--name-status", "--diff-filter=A", "origin/main...HEAD"])
    if code != 0:
        raise RuntimeError(err or "added test diff failed")
    added_tests = {line.split("\t", 1)[1] for line in added.splitlines()
                   if "\t" in line and is_test(line.split("\t", 1)[1])}
    code, tracked, err = _git(worktree, ["ls-files"])
    if code != 0:
        raise RuntimeError(err or "test paths lookup failed")
    tests = [path for path in tracked.splitlines() if is_test(path)]
    files = set()
    for path in failed:
        relative = path.removeprefix("./")
        if Path(path).is_absolute():
            try:
                relative = str(Path(path).relative_to(worktree))
            except ValueError:
                continue
        matches = [name for name in tests if name == relative or name.endswith("/" + relative)]
        # Package-local pytest paths must identify one file, not an existing namesake.
        if len(matches) == 1 and matches[0] in added_tests:
            files.add(matches[0])
    if not files:
        return None
    names = ", ".join(sorted(files))
    note = (f"Failing test(s) added by this PR: {names}\n{log[-6000:]}\n"
            "Fix the production code so they pass, or remove these newly added tests (new unit tests are not allowed).")
    rounds_append(picked["repo"], picked["issue"], "Fix → Build: failing test added in this PR: " + names)
    state_update(picked["repo"], picked["issue"], node="build", build_note=note,
                 result="running", reason=None, failures=0, retry_at=0)
    return {"next": "build"}


def fix_step(picked: dict, node: str, action, sha: str) -> dict:
    try:
        outcome = action()
    except Exception as exc:
        return needs_help(picked, f"{node}: {type(exc).__name__}: {exc}", sha)
    if node == "fix_code" and outcome.get("next") == "build":
        return outcome
    expected = "done" if node == "fix_code" else "pushed"
    if outcome.get("result") != expected and not (
        node == "fix_publish" and outcome.get("result") == "remote_moved" and outcome.get("sha")
    ):
        return needs_help(picked, f"{node}: {outcome}", sha)
    return outcome


def pushed_pr(repo: str, branch: str, sha: str) -> dict | None:
    for attempt in range(6):
        pr = open_pr_for(repo, branch)
        if pr and pr.get("headRefOid") == sha:
            return pr
        if attempt < 5:
            time.sleep(5)
    return None


@guarded_step
def resume(picked: dict) -> dict:
    from lokay.git import _git

    repo = next(row for row in load_repos() if row["name"] == picked["repo"])
    root = Path(os.path.expanduser(repo["clone_path"]))
    worktree = root.parent / f"{root.name}-wt-{picked['issue']}"
    branch = f"lokay/{picked['issue']}"
    try:
        pr = open_pr_for(picked["repo"], branch)
    except Exception as exc:
        return needs_help(picked, f"resume PR: {type(exc).__name__}: {exc}")
    if not pr or not pr.get("headRefOid"):
        return needs_help(picked, "resume PR missing or missing SHA")
    sha = pr["headRefOid"]
    state_update(picked["repo"], picked["issue"], pr=pr["number"])
    # open_pr_for filters by branch; its contract returns number and SHA only.
    if pr.get("headRefName", branch) != branch or (picked.get("pr") and picked["pr"] != pr["number"]):
        return needs_help(picked, "PR branch or number mismatch", sha)
    if not worktree.is_dir():
        return needs_help(picked, "missing worktree", sha)
    try:
        code, out, err = _git(worktree, ["branch", "--show-current"])
    except Exception as exc:
        return needs_help(picked, f"branch mismatch: {type(exc).__name__}: {exc}", sha)
    if code != 0 or out.strip() != branch:
        return needs_help(picked, f"branch mismatch: {err.strip() or out.strip()}", sha)
    from lokay.build import tidy_and_commit
    from lokay.fix import fix_publish

    tidy_and_commit(worktree, "lokay resume")
    code, out, err = _git(worktree, ["fetch", "origin", branch])
    if code != 0:
        return needs_help(picked, f"resume fetch: {err.strip() or out.strip()}", sha)
    code, out, err = _git(worktree, ["rev-parse", "HEAD"])
    if code != 0:
        return needs_help(picked, f"resume HEAD: {err.strip() or out.strip()}", sha)
    local = out.strip()
    if local != sha:
        ahead, out, err = _git(worktree, ["merge-base", "--is-ancestor", sha, local])
        if ahead not in (0, 1):
            return needs_help(picked, f"resume ancestry: {err.strip() or out.strip()}", sha)
        behind = 1
        if ahead != 0:
            behind, out, err = _git(worktree, ["merge-base", "--is-ancestor", local, sha])
            if behind not in (0, 1):
                return needs_help(picked, f"resume ancestry: {err.strip() or out.strip()}", sha)
            code, out, err = _git(worktree, ["merge", "--ff-only" if behind == 0 else "--no-edit", f"origin/{branch}"])
            if code != 0:
                reason = "sha diverged: conflict" if behind != 0 else f"resume ff: {err.strip() or out.strip()}"
                return needs_help(picked, reason, sha)
        if behind != 0:
            published = fix_step(picked, "fix_publish", lambda: fix_publish(worktree, branch, sha), sha)
            if published.get("result") != "pushed":
                if published.get("result") == "failed":
                    return published
                return needs_help(picked, f"fix_publish: {published}", sha)
            code, out, err = _git(worktree, ["rev-parse", "HEAD"])
            pr = pushed_pr(picked["repo"], branch, out.strip()) if code == 0 else None
            if code != 0 or not pr:
                return needs_help(picked, "sha mismatch after push", sha)
            sha = out.strip()
            _retry(picked, "fix", lambda: refresh_body(picked["repo"], int(picked["issue"])), "updated")
    code, out, err = _git(worktree, ["rev-parse", "HEAD"])
    if code != 0 or out.strip() != sha:
        return needs_help(picked, f"sha mismatch: {err.strip() or out.strip()}", sha)
    saved = state_read(picked["repo"], picked["issue"])
    if saved.get("sha") != sha or (saved.get("verdict") or {}).get("sha") != sha:
        state_update(picked["repo"], picked["issue"], node="check", verdict=None, fix_fingerprint=None)
    state_update(picked["repo"], picked["issue"], sha=sha)
    return _finish(picked, worktree, branch, sha, repo.get("test") or [])


def _finish(picked: dict, worktree: Path, branch: str, sha: str, tests: list, plan_rounds: int = 1) -> dict:
    from lokay.check import aggregate, check_state, decide_batches, hunks, local_ci
    from lokay.decide import decide
    from lokay.fix import fix_code, fix_publish
    from lokay import plan
    from lokay.git import _git
    from lokay.gh import _gh, open_pr_for, pr_checks, check_comment
    from lokay.merge import merge_sha
    from lokay.run import run_process

    repo = next(row for row in load_repos() if row["name"] == picked["repo"])
    clone_path = Path(os.path.expanduser(repo["clone_path"]))
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
        code, out, err = _git(worktree, ["merge", "--no-edit", "origin/main"])
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
                try:
                    merged = merge_sha(
                        picked["repo"], pr["number"], sha, verdict, worktree,
                        picked.get("held"), picked["repo"].split("/")[0], int(picked["issue"]),
                        {"plan_rounds": plan_rounds, "check_rounds": rounds},
                        clone_path=clone_path,
                    )
                except Exception as exc:
                    return needs_help(picked, f"merge: {type(exc).__name__}: {exc}", sha)
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
                pr = _retry(picked, "check", lambda: open_pr_for(picked["repo"], branch))
                if pr:
                    _retry(picked, "check", lambda: check_comment(picked["repo"], pr["number"],
                           rounds + 1, verdict, {"result": "conflict"}))
            else:
                pushed = fix_step(picked, "fix_publish", lambda: fix_publish(worktree, branch, sha), sha)
                if pushed["result"] == "failed":
                    return pushed
                if pushed["result"] == "remote_moved" and pushed.get("sha"):
                    _retry(picked, "check", sync_head)
                    sha = pushed["sha"]
                    pending = "check"
                    continue
                if pushed["result"] != "pushed":
                    raise RuntimeError(f"main synchronization publish failed: {pushed}")
                sha = pushed["sha"]
                if not pushed_pr(picked["repo"], branch, sha):
                    return needs_help(picked, "sha mismatch after push", sha)
                _retry(picked, "check", lambda: refresh_body(picked["repo"], int(picked["issue"])), "updated")
                state_update(picked["repo"], picked["issue"], sha=sha, verdict=None)
        def read_diff():
            diff = run_process(["git", "diff", "origin/main...HEAD"], cwd=worktree, timeout=30)
            if diff.returncode != 0:
                raise RuntimeError(diff.stderr or "diff failed")
            return diff
        diff = _retry(picked, "check", read_diff)
        diff_fingerprint = hashlib.sha256((diff.stdout or "").encode()).hexdigest()
        state_update(picked["repo"], picked["issue"], diff_fingerprint=diff_fingerprint)
        if pending == "fix" and verdict:
            uwagi = verdict["uwagi"]
            findings = {
                json.dumps([row.get("plik"), row.get("pytanie", row.get("warstwa")),
                            row.get("linia", row.get("linia_od")), row.get("linia_do")])
                for row in uwagi
            }
            fingerprint = hashlib.sha256(json.dumps(sorted(findings)).encode()).hexdigest()
            saved = state_read(picked["repo"], picked["issue"])
            art = run_dir(picked["repo"], picked["issue"]) / "plan.md"
            if saved.get("fix_fingerprint") == fingerprint:
                redirected = fix_to_build(picked, worktree)
                if redirected:
                    return redirected
                rounds_append(picked["repo"], picked["issue"], "Fix → Plan: no progress, findings=" + fingerprint)
                title, body = saved.get("issue_title"), saved.get("issue_body")
                if not title:
                    def read_issue():
                        code, raw, err = _gh(["issue", "view", str(picked["issue"]),
                                              "--repo", picked["repo"], "--json", "title,body"])
                        if code != 0:
                            raise RuntimeError(err or "issue view failed")
                        return json.loads(raw)
                    issue = _retry(picked, "plan", read_issue)
                    title, body = issue["title"], issue.get("body")
                prompt = plan.prompt_for(title, body) + (
                    "\n\nUwagi:\n" + json.dumps(uwagi)
                    + "\n\nRounds:\n" + (art.parent / "rounds.md").read_text()
                    + "\n\nTest log:\n" + (saved.get("test_log") or "")
                    + "\n\nPrevious plan:\n" + (art.read_text() if art.is_file() else "")
                    + "\nFix made no progress; revise the plan.\n"
                )
                state_update(picked["repo"], picked["issue"], node="plan", plan_phase="write",
                             plan_prompt=prompt, plan_evaluations=0, plan_accepted_sha=None)
                prepared = _prepare({**picked, "node": "plan"})
                if isinstance(prepared, dict):
                    return prepared
                worktree, branch, sha, tests, plan_rounds = prepared
                pending = "check"
                continue
            prompt = (
                Path(__file__).resolve().parents[2].joinpath("prompts/fix.md").read_text()
                + "\n\nSHA:\n" + sha
                + "\n\nUwagi:\n" + json.dumps(uwagi)
                + "\n\nDiff:\n" + (diff.stdout or "")[:20000]
                + "\n\nTest log:\n" + (saved.get("test_log") or "")
                + "\n\nPlan:\n" + (art.read_text() if art.is_file() else "")
                + "\n\nPrevious failure:\n" + (saved.get("fix_reason") or "")
            )
            from lokay.setup import prepare_dependencies

            prepare_dependencies(worktree, repo, int(picked["issue"]))
            def fix_action():
                outcome = fix_code(worktree, sha, prompt, dict(os.environ), clone_path=clone_path)
                if outcome.get("result") == "no_changes" or outcome.get("reason") == "no_changes":
                    redirected = fix_to_build(picked, worktree)
                    if redirected:
                        return redirected
                return outcome
            fixed = fix_step(picked, "fix_code", fix_action, sha)
            if fixed.get("next") == "build":
                return fixed
            if fixed["result"] == "failed":
                return fixed
            pushed = fix_step(picked, "fix_publish", lambda: fix_publish(worktree, branch, sha), sha)
            if pushed["result"] == "failed":
                return pushed
            if pushed["result"] == "remote_moved" and pushed.get("sha"):
                _retry(picked, "check", sync_head)
            sha = pushed["sha"]
            if pushed["result"] == "pushed":
                if not pushed_pr(picked["repo"], branch, sha):
                    return needs_help(picked, "sha mismatch after push", sha)
                _retry(picked, "fix", lambda: refresh_body(picked["repo"], int(picked["issue"])), "updated")
            state_update(picked["repo"], picked["issue"], sha=sha, fix_reason=None, fix_fingerprint=fingerprint)
            rounds_append(picked["repo"], picked["issue"], f"Fix: sha={sha}")
            pending = "check"
            continue
        rows = hunks(diff.stdout or "")
        saved = state_read(picked["repo"], picked["issue"])
        ci = saved.get("local_ci")
        if not tests or not ci or ci.get("sha") != sha or ci.get("argv") != tests:
            ci = _retry(picked, "check", lambda: local_ci(sha, [tests] if tests else [], worktree))
            ci = {**ci, "argv": list(tests)}
            state_update(picked["repo"], picked["issue"], local_ci=ci, test_log=ci["log"])
            if ci["notes"]:
                rounds_append(picked["repo"], picked["issue"], f"Check: sha={sha}, flaky=" + json.dumps(ci["notes"]))
        log = ci["log"]
        directory = run_dir(picked["repo"], picked["issue"])
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"check-{rounds + 1}-diff.patch").write_text(diff.stdout or "")
        (directory / f"check-{rounds + 1}-test.log").write_text(log)
        pr = _retry(picked, "check", lambda: open_pr_for(picked["repo"], branch))
        if not pr:
            raise RuntimeError("PR missing during Check")
        remote = _retry(picked, "check", lambda: pr_checks(picked["repo"], pr["number"], sha))
        if remote["result"] == "sha_moved":
            _retry(picked, "check", sync_head)
            sha = remote["sha"]
            pending = "check"
            continue
        if remote["result"] == "pending":
            state_update(picked["repo"], picked["issue"], node="check", result="pending", verdict=None)
            rounds_append(picked["repo"], picked["issue"], f"Check: sha={sha}, GitHub CI pending")
            _retry(picked, "check", lambda: check_comment(picked["repo"], pr["number"], rounds + 1,
                   {"result": "pending", "sha": sha, "uwagi": []}, remote))
            return {"result": "pending", "sha": sha}
        ci = {**ci, "failed": ci["failed"] + [
            {"warstwa": "GitHub CI", "plik": "", "log": name}
            for name in remote.get("failed") or []
        ], "result": "green" if ci["result"] == remote["result"] == "green" else "red"}
        def read_stat():
            stat = run_process(["git", "diff", "--stat", "origin/main...HEAD"], cwd=worktree, timeout=30)
            if stat.returncode != 0:
                raise RuntimeError(stat.stderr or "diff stat failed")
            return stat.stdout or ""

        directory = run_dir(picked["repo"], picked["issue"])
        art = directory / "plan.md"
        decision_state = check_state(directory, rounds + 1, diff.stdout or "",
                                     _retry(picked, "check", read_stat), ci,
                                     sha=sha, repo=picked["repo"], issue=picked["issue"],
                                     plan=art.read_text() if art.is_file() else "")
        decisions = []
        kinds = ("correctness alignment architecture security production scope tests",)
        for kind in kinds:
            decision = decide_batches(kind, rows, {**decision_state, "kind": kind},
                                      lambda request: _retry(picked, "check", lambda: decide(request)))
            decision["sha"] = sha
            decisions.append(decision)
        verdict = aggregate(sha, ci, decisions)
        from lokay.scope import code_scope_issue

        code, changed, err = _git(worktree, ["diff", "--name-only", "origin/main...HEAD"])
        if code != 0:
            raise RuntimeError(err or "scope diff failed")
        files = changed.splitlines()
        saved = state_read(picked["repo"], picked["issue"])
        if files and not saved.get("issue_title"):
            code, raw, err = _gh(["issue", "view", str(picked["issue"]), "--repo", picked["repo"], "--json", "title,body"])
            if code != 0:
                raise RuntimeError(err or "issue view failed")
            issue = json.loads(raw)
            state_update(picked["repo"], picked["issue"], issue_title=issue["title"], issue_body=issue.get("body"))
            saved = state_read(picked["repo"], picked["issue"])
        scope = code_scope_issue(files, saved.get("issue_title") or "", saved.get("issue_body"))
        if scope:
            verdict = {**verdict, "result": "fix", "uwagi": [*verdict.get("uwagi", []), scope]}
        rounds += 1
        state_update(
            picked["repo"], picked["issue"], node="check", sha=sha,
            check_rounds=rounds, result=verdict["result"], verdict=verdict, test_log=log,
        )
        counts = ", ".join(
            f"{kind}={len(decision['uwagi'])}"
            for kind, decision in zip(kinds, decisions)
        )
        rounds_append(
            picked["repo"], picked["issue"],
            f"Check {rounds}: sha={sha}, result={verdict['result']}, uwagi: {counts}, ci={ci['result']}",
        )
        _retry(picked, "check", lambda: check_comment(picked["repo"], pr["number"], rounds, verdict, ci))
        pending = verdict["result"]
        state_update(picked["repo"], picked["issue"], node=pending)
