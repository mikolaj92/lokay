from __future__ import annotations

from dataclasses import asdict
from json import dumps

import tempfile
import time
from pathlib import Path

from lokay.config import repo as repo_config
from lokay.effects.gh import gh_json, gh_ok, fit_body
from lokay.effects.git import git, base_branch, worktree_remove
from lokay.store import main_status, save_main_status
from lokay.types import Finding, parse_finding

TITLE = "lokay: main czerwony"
MARKER = "lokay-main-red"
GUARD_VERSION = 1


def run_repo_tests(repo: dict, sha: str, worktree: Path) -> dict:
    from lokay.effects.tests import local_ci

    tests = repo.get("test") or []
    result = local_ci(sha, [tests] if tests else [], worktree, timeout=repo.get("test_timeout", 600))
    result["syntax_only"] = repo.get("syntax_only", False)
    return result


def guard_issues(repo: str, state: str = "all") -> list[dict]:
    rows = gh_json(["issue", "list", "--repo", repo, "--state", state,
                    "--limit", "1000000", "--json", "number,title,body,state"],
                   error="main issue lookup failed", strip=False, default="[]")
    return [row for row in rows
            if row["title"] == TITLE or MARKER in (row.get("body") or "")]


def guard_issue(repo: str, body: str) -> int:
    matches = guard_issues(repo)
    text = fit_body(f"<!-- {MARKER} -->\n{body}")
    if matches:
        issue = min(matches, key=lambda row: int(row["number"]))
        number = int(issue["number"])
        gh_ok(["issue", "edit", str(number), "--repo", repo,
               "--title", TITLE, "--body", text], error="main issue edit failed", strip=False)
        if issue.get("state") == "CLOSED":
            gh_ok(["issue", "reopen", str(number), "--repo", repo],
                  error="main issue reopen failed", strip=False)
        return number
    out = gh_ok(["issue", "create", "--repo", repo, "--title", TITLE, "--body", text],
                error="main issue create failed", strip=False)
    return int(out.strip().rstrip("/").rsplit("/", 1)[1])


def check_main(repo: str, clone_path: Path, merge_sha: str | None = None, pr: int | None = None, *, base: str | None = None, config: dict | None = None, force: bool = False, revision: str | None = None) -> dict:
    from lokay.checks import CheckInput, lockfile

    if config is None:
        config = repo_config(repo)

    base = base or base_branch(clone_path)
    git(clone_path, "fetch", "origin", base, timeout=60)
    sha = git(clone_path, "rev-parse", revision or f"origin/{base}", timeout=60)
    previous = main_status().get(repo, {})
    baseline = previous.get("baseline", {})
    argv = config.get("test") or []
    if (force or revision or baseline.get("sha") != sha or baseline.get("argv") != argv
            or baseline.get("guard_version") != GUARD_VERSION
            or baseline.get("lockfile", {}).get("status") not in ("pass", "fail")
            or baseline.get("ci", {}).get("tested") is not True):
        with tempfile.TemporaryDirectory(prefix="lokay-main-") as temporary:
            worktree = Path(temporary) / "checkout"
            git(clone_path, "worktree", "add", "--detach", str(worktree), sha, timeout=60)
            try:
                from lokay.setup import prepare_dependencies

                setup = prepare_dependencies(worktree, config, pr or 0)
                setup = setup if isinstance(setup, dict) else {}
                ci = run_repo_tests(config, sha, worktree)
                ci["log"] = setup.get("log", "") + "\n" + ci["log"]
                if setup.get("failed"):
                    ci.update(result="red", tested=False, failed=[*setup["failed"], *ci["failed"]])
                lock = lockfile(CheckInput(repo, pr or 0, sha, "", "", "", [], ci, worktree))
                baseline = {"sha": sha, "argv": argv, "guard_version": GUARD_VERSION,
                            "ci": ci, "lockfile": asdict(lock)}
            finally:
                cleanup = worktree_remove(clone_path, worktree)
                if cleanup["result"] != "removed":
                    raise RuntimeError(cleanup.get("error") or "worktree cleanup failed")
    ci = baseline["ci"]
    tested = ci.get("tested") is True
    lock = baseline["lockfile"]
    status = ("red" if lock["status"] == "fail" or (tested and ci["result"] != "green")
              else "green" if tested and lock["status"] == "pass" else "unknown")
    if revision:
        return {"status": status, "baseline": baseline}
    culprit = ({"sha": merge_sha, "pr": pr} if merge_sha and pr else previous.get("culprit"))
    if not (merge_sha and pr) and sha != previous.get("baseline", {}).get("sha"):
        culprit = None
        if status != "green":
            pulls = gh_json(["api", f"repos/{repo}/commits/{sha}/pulls"], error="main culprit lookup failed")
            culprit = next(({"sha": sha, "pr": row["number"]} for row in pulls
                            if row.get("merged_at") and row.get("merge_commit_sha") == sha), None)
    result = {"status": status,
              "since": previous.get("since", time.time()) if previous.get("status") == status else time.time(),
              "culprit": culprit, "issue": previous.get("issue"), "baseline": baseline,
              "checked_at": time.time(),
              "exhausted_sha": previous.get("exhausted_sha")}
    if status == "red" or (status == "unknown" and time.time() - result["since"] >= 3600):
        save_main_status(repo, result)
        diff = git(clone_path, "show", "--format=fuller", "--first-parent", merge_sha, timeout=60) if merge_sha else ""
        lock_log = "\n".join(
            f"{item.plik}:{item.linia_od}: {item.zmiana}" for raw in lock["findings"]
            if isinstance(item := parse_finding(raw), Finding))
        body = (f"Main {status}. Napraw przez Plan → Build → Check → Fix → Merge.\n"
                f"Culprit: {dumps(culprit)} · tested SHA: `{sha}`\n\n"
                f"Diff:\n```diff\n{diff[:12000]}\n```\n\n"
                f"Test log (tested={ci.get('tested', False)}):\n```\n{ci['log'][-12000:]}\n```\n\n"
                f"Lock checks ({lock['status']}):\n```\n{lock['reason']}\n{lock_log}\n```")
        if result["exhausted_sha"] != sha:
            result["issue"] = guard_issue(repo, body)
            from lokay.store import state_read, state_update

            state = state_read(repo, result["issue"])
            if previous.get("exhausted_sha") or (
                state.get("result") in ("merged", "closed", "failed", "empty_patch")
                and sha not in (state.get("recovery_sha"), state.get("sha"))
            ):

                state_update(repo, result["issue"], _event={"action": "reopened", "outcome": {"issue": True, "main_sha": sha}},
                             children=[], split_tasks=None, recovery_sha=None, recovery_exhausted=False,
                             h2_context=None, difficulty=None, issue_body=body)
                result["exhausted_sha"] = None
    elif status == "green":
        matches = [issue for issue in guard_issues(repo, "open") if issue.get("state") == "OPEN"]
        if matches:
            number = int(min(matches, key=lambda row: int(row["number"]))["number"])
            body = (f"Main zielony. Tested SHA: `{baseline['sha']}`\n"
                    f"argv: `{dumps(baseline['argv'])}`\n"
                    f"Executed tests: {ci.get('executed', 0)}\n"
                    f"Lock checks: {lock['status']}")
            gh_ok(["issue", "close", str(number), "--repo", repo, "--comment", body],
                  error="main issue close failed", strip=False)
            result["issue"] = number
    save_main_status(repo, result)
    return result


def local_baseline(repo: str, clone_path: Path, ci: dict, *, base: str | None = None) -> dict:
    from lokay.review import test_failures

    main = check_main(repo, clone_path, base=base)["baseline"]
    if (ci.get("tested") is not True
            or main["ci"].get("tested") is not True or main["ci"]["result"] != "red") or any(
        item.get("warstwa") == "setup" for item in main["ci"].get("failed", [])
    ):
        return ci
    failures = test_failures(ci["log"])
    inherited = test_failures(main["ci"]["log"])
    if not failures or not inherited:
        return ci
    novel = sorted(failures - inherited)
    failed = [{"warstwa": "tests", "plik": item, "log": item} for item in novel]
    return {**ci, "baseline": {"sha": main["sha"], "failures": sorted(inherited)},
            "result": "red" if novel else "green", "failed": failed,
            "tested": ci.get("tested", False) or not novel}
