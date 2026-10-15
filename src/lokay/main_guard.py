from __future__ import annotations

from json import dumps

import json
import tempfile
import time
from pathlib import Path

from lokay.config import load_repos
from lokay.gh import _gh, fit_body
from lokay.git import _git
from lokay.store import main_status, save_main_status

TITLE = "lokay: main czerwony"
MARKER = "lokay-main-red"


def run_repo_tests(repo: dict, sha: str, worktree: Path) -> dict:
    from lokay.check import local_ci

    tests = repo.get("test") or []
    return local_ci(sha, [tests] if tests else [], worktree, timeout=repo.get("test_timeout", 600))


def guard_issue(repo: str, body: str) -> int:
    code, out, err = _gh(["issue", "list", "--repo", repo, "--state", "all",
                          "--limit", "1000000", "--json", "number,title,body,state"])
    if code:
        raise RuntimeError(err or "main issue lookup failed")
    matches = [row for row in json.loads(out or "[]")
               if row["title"] == TITLE or MARKER in (row.get("body") or "")]
    text = fit_body(f"<!-- {MARKER} -->\n{body}")
    if matches:
        issue = min(matches, key=lambda row: int(row["number"]))
        number = int(issue["number"])
        code, _, err = _gh(["issue", "edit", str(number), "--repo", repo,
                            "--title", TITLE, "--body", text])
        if code:
            raise RuntimeError(err or "main issue edit failed")
        if issue.get("state") == "CLOSED":
            code, _, err = _gh(["issue", "reopen", str(number), "--repo", repo])
            if code:
                raise RuntimeError(err or "main issue reopen failed")
        return number
    code, out, err = _gh(["issue", "create", "--repo", repo, "--title", TITLE, "--body", text])
    if code:
        raise RuntimeError(err or "main issue create failed")
    return int(out.strip().rstrip("/").rsplit("/", 1)[1])


def check_main(repo: str, clone_path: Path, merge_sha: str | None = None, pr: int | None = None) -> dict:
    config = next(row for row in load_repos() if row["name"] == repo)

    def git(path, args):
        code, out, err = _git(path, args)
        if code:
            raise RuntimeError(err or out)
        return out.strip()

    git(clone_path, ["fetch", "origin", "main"])
    sha = git(clone_path, ["rev-parse", "origin/main"])
    previous = main_status().get(repo, {})
    baseline = previous.get("baseline", {})
    argv = config.get("test") or []
    if baseline.get("sha") != sha or baseline.get("argv") != argv:
        with tempfile.TemporaryDirectory(prefix="lokay-main-") as temporary:
            worktree = Path(temporary) / "checkout"
            git(clone_path, ["worktree", "add", "--detach", str(worktree), sha])
            try:
                from lokay.setup import prepare_dependencies

                setup = prepare_dependencies(worktree, config, pr or 0)
                setup = setup if isinstance(setup, dict) else {}
                ci = run_repo_tests(config, sha, worktree)
                ci["log"] = setup.get("log", "") + "\n" + ci["log"]
                if setup.get("failed"):
                    ci.update(result="red", tested=False, failed=[*setup["failed"], *ci["failed"]])
                baseline = {"sha": sha, "argv": argv, "ci": ci}
            finally:
                git(clone_path, ["worktree", "remove", "--force", str(worktree)])
    ci = baseline["ci"]
    green = ci.get("tested") is True and ci["result"] == "green"
    status = "green" if green else "red"
    culprit = {"sha": merge_sha or sha, "pr": pr}
    result = {"status": status,
              "since": previous.get("since", time.time()) if previous.get("status") == status else time.time(),
              "culprit": culprit, "issue": previous.get("issue"), "baseline": baseline}
    if not green:
        diff = git(clone_path, ["show", "--format=fuller", "--first-parent", merge_sha]) if merge_sha else ""
        body = (f"Main czerwony. Napraw przez Plan → Build → Check → Fix → Merge.\n"
                f"Culprit: {dumps(culprit)} · tested SHA: `{sha}`\n\n"
                f"Diff:\n```diff\n{diff[:12000]}\n```\n\n"
                f"Test log (tested={ci.get('tested', False)}):\n```\n{ci['log'][-12000:]}\n```")
        result["issue"] = guard_issue(repo, body)
    save_main_status(repo, result)
    return result


def local_baseline(repo: str, clone_path: Path, ci: dict) -> dict:
    from lokay.check import test_failures

    main = check_main(repo, clone_path)["baseline"]
    if main["ci"]["result"] != "red" or any(
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


def pre_deploy(repo: str, sha: str) -> dict:
    return {"pass": True}
