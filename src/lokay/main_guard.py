from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

from lokay.config import load_repos
from lokay.gh import _gh, fit_body
from lokay.git import _git
from lokay.state import main_status, save_main_status

TITLE = "lokay: main czerwony"
MARKER = "lokay-main-red"


def run_repo_tests(repo: dict, sha: str, worktree: Path) -> dict:
    from lokay.check import local_ci

    tests = repo.get("test") or []
    return local_ci(sha, [tests] if tests else [], worktree)


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


def check_main(repo: str, clone_path: Path, merge_sha: str, pr: int) -> dict:
    config = next(row for row in load_repos() if row["name"] == repo)

    def git(path, args):
        code, out, err = _git(path, args)
        if code:
            raise RuntimeError(err or out)
        return out.strip()

    git(clone_path, ["fetch", "origin", "main"])
    sha = git(clone_path, ["rev-parse", "origin/main"])
    with tempfile.TemporaryDirectory(prefix="lokay-main-") as temporary:
        worktree = Path(temporary) / "checkout"
        git(clone_path, ["worktree", "add", "--detach", str(worktree), sha])
        try:
            from lokay.setup import prepare_dependencies

            setup = prepare_dependencies(worktree, config, pr)
            setup = setup if isinstance(setup, dict) else {}
            ci = run_repo_tests(config, sha, worktree)
            ci["log"] = setup.get("log", "") + "\n" + ci["log"]
            green = ci.get("tested") is True and ci["result"] == "green" and not setup.get("failed")
            diff = git(worktree, ["show", "--format=fuller", "--first-parent", merge_sha])
            previous = main_status().get(repo, {})
            status = "green" if green else "red"
            result = {"status": status,
                      "since": previous.get("since", time.time()) if previous.get("status") == status else time.time(),
                      "culprit": {"sha": merge_sha, "pr": pr}, "issue": previous.get("issue")}
            if not green:
                body = (f"Main czerwony. Napraw przez Plan → Build → Check → Fix → Merge.\n"
                        f"Merge SHA: `{merge_sha}` · PR: #{pr} · tested SHA: `{sha}`\n\n"
                        f"Diff:\n```diff\n{diff[:12000]}\n```\n\n"
                        f"Test log (tested={ci.get('tested', False)}):\n```\n{ci['log'][-12000:]}\n```")
                result["issue"] = guard_issue(repo, body)
            save_main_status(repo, result)
            return result
        finally:
            git(clone_path, ["worktree", "remove", "--force", str(worktree)])


def pre_deploy(repo: str, sha: str) -> dict:
    return {"pass": True}
