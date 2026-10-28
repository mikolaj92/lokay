from __future__ import annotations

from dataclasses import asdict
from json import dumps

import tempfile
import time
from pathlib import Path

from lokay.config import repo as repo_config
from lokay.effects.gh import gh_json, gh_ok, fit_body
from lokay.effects.git import git, base_branch, worktree_remove
from lokay.store import main_baseline, main_status, save_base_test, save_main_status
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
    from lokay.store import state_read, state_update
    from lokay.tick import RECOVERY_EVIDENCE

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
    else:
        out = gh_ok(["issue", "create", "--repo", repo, "--title", TITLE, "--body", text],
                    error="main issue create failed", strip=False)
        number = int(out.strip().rstrip("/").rsplit("/", 1)[1])
    loaded = gh_json(["issue", "view", str(number), "--repo", repo, "--json", "title,body"],
                     error="main issue view failed")
    saved_body = state_read(repo, number).get("issue_body") or ""
    _, marker, suffix = saved_body.partition(RECOVERY_EVIDENCE)
    body = (loaded["body"] or "") + marker + suffix if marker else loaded["body"]
    state_update(repo, number, issue_title=loaded["title"], issue_body=body)
    return number


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
    base_test = {} if tested else main_baseline(repo, sha).get("base_test") or {}
    if base_test:
        baseline = {**baseline, "base_test": base_test}
    status = ("red" if lock["status"] == "fail" or (tested and ci["result"] != "green") or base_test
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
                + (f"Testy na bazie: {dumps(base_test.get('failed', []))}\n\n" if base_test else "")
                + f"Diff:\n```diff\n{diff[:12000]}\n```\n\n"
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


def base_tests(repo: str, clone_path: Path, baseline: dict, failures: set[str], config: dict | None = None) -> dict:
    from lokay.effects.git import git_try, worktree_remove
    from lokay.setup import prepare_dependencies

    argv = list(baseline.get("argv") or [])
    names = sorted(item for item in failures if "::" in item or item.endswith(".py"))
    if not argv or "-c" in argv or not any("pytest" in token for token in argv) or not names:
        return {}
    sha = baseline.get("sha") or ""
    probe_config = {"name": repo, "test": [*argv, *names],
                    "test_timeout": (config or {}).get("test_timeout", 600)}
    with tempfile.TemporaryDirectory(prefix="lokay-base-test-") as temporary:
        worktree = Path(temporary) / "checkout"
        code, _, _ = git_try(clone_path, "worktree", "add", "--detach", str(worktree), sha, timeout=60)
        if code:
            worktree = clone_path
        try:
            prepare_dependencies(worktree, probe_config, 0)
            return {"sha": sha, "argv": probe_config["test"], **run_repo_tests(probe_config, sha, worktree)}
        finally:
            if worktree != clone_path:
                cleanup = worktree_remove(clone_path, worktree)
                if cleanup["result"] != "removed":
                    raise RuntimeError(cleanup.get("error") or "worktree cleanup failed")


def local_baseline(repo: str, clone_path: Path, ci: dict, *, base: str | None = None,
                   config: dict | None = None) -> dict:
    from lokay.review import log_excerpt, test_failures

    main = check_main(repo, clone_path, base=base)["baseline"]
    if ci.get("tested") is not True or ci.get("argv") != main.get("argv"):
        return ci
    failures = test_failures(ci["log"])
    if not failures:
        return ci
    probe = {}
    if main["ci"].get("tested") is True and main["ci"]["result"] == "red":
        inherited = test_failures(main["ci"]["log"])
    else:
        probe = base_tests(repo, clone_path, main, failures, config)
        if not probe:
            return ci
        inherited = {item for item in test_failures(probe.get("log", "")) if item in failures}
        if inherited:
            record = {"sha": main.get("sha"), "argv": probe["argv"], "failed": sorted(inherited),
                      "log": log_excerpt(probe.get("log", ""))}
            save_main_status(repo, {**main_status().get(repo, {}), "status": "red",
                                    "checked_at": time.time(), "baseline": {**main, "base_test": record}})
            save_base_test(repo, main.get("sha") or "", record)
    novel = sorted(failures - inherited)
    failed = [{"warstwa": "tests", "plik": item, "log": log_excerpt(ci["log"]),
               "on_main": False} for item in novel]
    baseline = {"sha": main["sha"], "argv": main.get("argv"),
                "failures": sorted(inherited), "inherited": sorted(failures & inherited)}
    if probe:
        baseline["base_test"] = {"sha": main.get("sha"), "argv": probe["argv"],
                                 "failed": sorted(inherited),
                                 "passed": probe.get("result") == "green"}
    return {**ci, "baseline": baseline, "result": "red" if novel else "green",
            "failed": failed, "tested": ci.get("tested", False) or not novel}
