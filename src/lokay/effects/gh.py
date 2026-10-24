from __future__ import annotations

from datetime import datetime
from json import dumps

import json
import logging
import os
import re
import shutil
import subprocess
from collections.abc import Mapping
from pathlib import Path

from lokay import store
from lokay.effects.pi import run_process
from lokay.effects.retry import retry
from lokay.redact import redact_text
from lokay.safety import SafetyError, validate_argv
from lokay.types import CheckResult, Note, parse_finding

ORIGIN = "lokay"
GH_CANDIDATES = (
    Path.home() / ".local/share/mise/installs/gh/2.102.0/gh_2.102.0_macOS_arm64/bin/gh",
    Path("/opt/homebrew/bin/gh"),
    Path("/usr/local/bin/gh"),
)


def fit_body(text: str, limit: int = 65536) -> str:
    if len(text) <= limit:
        return text
    notice = "\n... [{} znaków logu pominięto; pełny log w ~/.lokay/runs] ...\n"
    keep = limit - len(notice.format(len(text)))
    if keep < 2:
        raise ValueError("body limit is too small to keep the start and end")
    start = (keep + 1) // 2
    end = keep // 2
    return text[:start] + notice.format(len(text) - keep) + text[-end:]


def gh_bin() -> str:
    found = shutil.which("gh")
    if found:
        return found
    for path in GH_CANDIDATES:
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    return "gh"


def auth_status(env: Mapping[str, str]):
    return run_process([gh_bin(), "auth", "status"], env=env, timeout=15)


def _gh(args: list[str], env: Mapping[str, str] | None = None, *, cwd: Path | None = None) -> tuple[int, str, str]:
    args = [redact_text(arg, env) for arg in args]
    for index, arg in enumerate(args):
        if re.search(r"(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{20,}", arg):
            subcommand = " ".join(part if re.fullmatch(r"[a-z][a-z-]*", part) else "?" for part in args[:2])
            message = f"gh post blocked: GitHub token pattern survived redaction (arg {index}, {subcommand})"
            logging.getLogger(__name__).error(message)
            raise SafetyError(message)
    index = 0
    while index < len(args):
        arg = args[index]
        if arg in ("--body", "--title") and index + 1 < len(args):
            index += 1
            args[index] = fit_body(args[index]) if arg == "--body" else args[index][:256]
        elif arg.startswith("--body="):
            args[index] = "--body=" + fit_body(arg[len("--body="):])
        elif arg.startswith("--title="):
            args[index] = "--title=" + arg[len("--title="):][:256]
        index += 1
    validate_argv(["gh", *args])
    attempts = 1 if args[:2] == ["issue", "create"] else 4
    def transient(proc):
        if isinstance(proc, subprocess.TimeoutExpired):
            return "gh timed out"
        if isinstance(proc, Exception) or proc.returncode == 0:
            return None
        match = re.search(
            r"Something went wrong while executing your query|\bHTTP\s+(?:502|503|504)\b|"
            r"\btimeout\b|\btimed out\b|\bconnection reset\b|\bECONNRESET\b",
            (proc.stdout or "") + "\n" + (proc.stderr or ""), re.IGNORECASE,
        )
        return match[0] if match else None

    proc = retry(lambda: run_process([gh_bin(), *args], env=env, timeout=60,
                                    cwd=str(cwd) if cwd is not None else None), attempts, transient, call="gh")
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def gh_ok(args: list[str], *, error: str = "gh failed", strip: bool = True, include_stdout: bool = False,
          allow_partial_data: bool = False) -> str:
    code, out, err = _gh(args)
    if code != 0:
        if allow_partial_data:
            try:
                response = json.loads(out)
            except ValueError:
                pass
            else:
                if isinstance(response, dict) and isinstance(response.get("data"), dict):
                    return out
        reason = err.strip() if strip else err
        raise RuntimeError(reason or (out.strip() if include_stdout else "") or error)
    return out


def gh_json(args: list[str], *, error: str = "gh failed", strip: bool = True, default: str | None = None,
            allow_partial_data: bool = False):
    out = gh_ok(args, error=error, strip=strip, allow_partial_data=allow_partial_data)
    return json.loads(out if default is None else out or default)


def pr_closed_by_factory(repo: str, number: int) -> bool:
    owner, name = repo.split("/", 1)
    query = ('query($owner: String!, $name: String!, $number: Int!) {'
             ' viewer { login } repository(owner: $owner, name: $name) {'
             ' pullRequest(number: $number) {'
             ' timelineItems(itemTypes: [CLOSED_EVENT], last: 1) {'
             ' nodes { ... on ClosedEvent { actor { login } } } } } } }')
    response = gh_json(["api", "graphql", "-f", f"query={query}",
                        "-f", f"owner={owner}", "-f", f"name={name}", "-F", f"number={int(number)}"],
                       error="PR close actor lookup failed")
    if response.get("errors"):
        raise RuntimeError("PR close actor lookup failed")
    data = response["data"]
    viewer = (data.get("viewer") or {}).get("login")
    pr = (data.get("repository") or {}).get("pullRequest") or {}
    nodes = (pr.get("timelineItems") or {}).get("nodes") or []
    actor = ((nodes[-1] or {}).get("actor") or {}).get("login") if nodes else None
    return bool(viewer and actor == viewer)


def create_child_issue(repo: str, parent: int, index: int, task: dict, generation: int) -> int:
    marker = f"Lokay parent: #{parent}; split: {generation}; task: {index}"
    rows = gh_json(["issue", "list", "--repo", repo, "--state", "all", "--limit", "1000000",
                    "--json", "number,body"], error="child issue lookup failed", default="[]")
    for row in rows:
        if marker in (row.get("body") or "").splitlines():
            return int(row["number"])
    after = "\nLokay after: " + ", ".join(f"#{number}" for number in task["blocked_by"]) if task.get("blocked_by") else ""
    out = gh_ok(["issue", "create", "--repo", repo, "--title", task["title"],
                 "--body", marker + "\n\n" + task["body"] + after], error="child issue create failed")
    match = re.search(r"https://github\.com/" + re.escape(repo) + r"/issues/(\d+)\s*$", out)
    if not match:
        raise RuntimeError("child issue URL missing")
    return int(match[1])


def children_done(repo: str, children: list[int]) -> bool:
    owner, name = repo.split("/", 1)
    query = ('query($owner: String!, $name: String!, $issue: Int!, $head: String!) {'
             ' repository(owner: $owner, name: $name) { issue(number: $issue) { state }'
             ' pullRequests(headRefName: $head, states: MERGED, first: 1) { nodes { number } } } }')
    for issue in children:
        response = gh_json(["api", "graphql", "-f", f"query={query}",
                            "-f", f"owner={owner}", "-f", f"name={name}",
                            "-F", f"issue={issue}", "-f", f"head=lokay/{issue}"],
                           error="child merge lookup failed")
        if response.get("errors"):
            raise RuntimeError("child merge lookup failed")
        repository = response["data"]["repository"]
        state = repository["issue"]["state"]
        nodes = repository["pullRequests"]["nodes"]
        if state != "CLOSED" and not nodes:
            return False
    return bool(children)


def host_ops(body: str | None) -> bool:
    return "<!-- lokay-host-ops:" in (body or "")


def open_issues(repo: str) -> list[dict]:
    rows = gh_json(
        ["issue", "list", "--repo", repo, "--state", "open", "--limit", "1000000", "--json", "number,createdAt,title,labels,state,body"],
        error="issue list failed", default="[]",
    )
    rows = [row for row in rows if not host_ops(row.get("body"))]
    return sorted(rows, key=lambda row: (row["createdAt"], int(row["number"])))


def open_pr_for(repo: str, branch: str) -> dict | None:
    rows = gh_json(
        ["pr", "list", "--repo", repo, "--head", branch, "--state", "open", "--json", "number,headRefOid,baseRefName"],
        error="pr list failed", default="[]",
    )
    return rows[0] if rows else None


def pr_files(repo: str, number: int) -> list[str]:
    out = gh_ok(["api", "--paginate", f"repos/{repo}/pulls/{number}/files", "--jq", ".[].filename"],
                error="PR files lookup failed")
    return out.splitlines()


def pr_create(repo: str, branch: str, title: str, body: str, issue: int) -> dict:
    marked = body.rstrip() + f"\n\nCloses #{issue}\n\nOpened by {ORIGIN}.\n"
    code, out, err = _gh(
        ["pr", "create", "--repo", repo, "--head", branch, "--title", title, "--body", fit_body(marked)]
    )
    if code != 0:
        if "already exists" in err:
            pr = open_pr_for(repo, branch)
            if pr:
                return {"result": "pr_open", "url": f"https://github.com/{repo}/pull/{pr['number']}"}
        raise RuntimeError(err.strip() or "pr create failed")
    return {"result": "pr_open", "url": out.strip()}


def pr_set_body(repo: str, number: int, body: str, issue: int) -> dict:
    marked = body.rstrip() + f"\n\nCloses #{issue}\n\nOpened by {ORIGIN}.\n"
    gh_ok(["pr", "edit", str(number), "--repo", repo, "--body", fit_body(marked)], error="pr edit failed")
    return {"result": "updated", "pr": number}


def pr_checks(repo: str, number: int, sha: str) -> dict:
    view = gh_json(["pr", "view", str(number), "--repo", repo, "--json", "statusCheckRollup,headRefOid"],
                   error="pr view failed")
    if view.get("headRefOid") != sha:
        return {"result": "sha_moved", "sha": view.get("headRefOid") or ""}
    rollup = view.get("statusCheckRollup") or []
    if not rollup:
        code, out, err = _gh(["api", f"repos/{repo}/contents/.github/workflows?ref={sha}"])
        if code and "404" not in err:
            raise RuntimeError(err.strip() or "workflow lookup failed")
        workflows = [] if code else json.loads(out)
        if any(item.get("type") == "file" and Path(item["path"]).suffix in (".yml", ".yaml")
               for item in workflows):
            return {"result": "pending", "sha": sha, "failed": [], "pending": ["GitHub workflows"]}
        return {"result": "no_ci", "sha": sha, "failed": [],
                "notes": [{"warstwa": "GitHub CI", "log": "no GitHub checks configured"}]}
    active_checks = {
        (item.get("workflowName"), item.get("name"))
        for item in rollup
        if item.get("__typename") == "CheckRun" and item.get("conclusion") != "CANCELLED"
    }
    rollup = [
        item for item in rollup
        if not (item.get("__typename") == "CheckRun" and item.get("conclusion") == "CANCELLED"
                and (item.get("workflowName"), item.get("name")) in active_checks)
    ]
    failed = []
    failed_logs = {}
    jobs = {}
    pending = []
    for item in rollup:
        name = item.get("name") or item.get("context") or "GitHub CI"
        failure_count = len(failed)
        if item.get("__typename") == "StatusContext" or "state" in item:
            if item.get("state") in ("ERROR", "FAILURE"):
                failed.append(name)
            elif item.get("state") != "SUCCESS":
                pending.append(name)
        elif item.get("status") != "COMPLETED":
            pending.append(name)
        elif item.get("conclusion") not in ("SUCCESS", "NEUTRAL", "SKIPPED"):
            failed.append(name)
        if len(failed) > failure_count:
            failed_logs[name] = name
            identity = re.search(r"/actions/runs/(\d+)/job/(\d+)(?:/|$)", item.get("detailsUrl") or "")
            if item.get("__typename") == "CheckRun" and identity and item.get("startedAt"):
                jobs[name] = {"run": identity[1], "job": identity[2], "started": item["startedAt"]}
            run = re.search(r"/actions/runs/(\d+)(?:/|$)", item.get("detailsUrl") or "")
            if run:
                try:
                    code, log, _ = _gh(["run", "view", run[1], "--repo", repo, "--log-failed"])
                    if code == 0 and log.strip():
                        failed_logs[name] = log[-4000:]
                except Exception:
                    pass
    if pending:
        return {"result": "pending", "sha": sha, "failed": failed,
                "failed_logs": failed_logs, "pending": pending}
    if failed:
        return {"result": "red", "sha": sha, "failed": failed, "failed_logs": failed_logs, "jobs": jobs}
    return {"result": "green", "sha": sha, "failed": []}


def main_inherited(repo, main_sha, remote, touched_workflows):
    jobs = remote.get("jobs") or {}
    if remote["result"] != "red" or touched_workflows or any(name not in jobs for name in remote["failed"]):
        return remote
    runs = gh_json(["api", "--paginate", "--slurp", f"repos/{repo}/commits/{main_sha}/check-runs?per_page=100"],
                   error="main checks lookup failed")
    latest = {}
    for page in runs:
        for run in page["check_runs"]:
            name = run["name"]
            if name not in latest or run["id"] > latest[name]["id"]:
                latest[name] = run
    if any(name not in latest for name in remote["failed"]):
        return remote
    identities = {}
    stale = False
    refreshed = set()
    for name in remote["failed"]:
        run = latest[name]
        identity = re.search(r"/actions/runs/(\d+)/job/(\d+)(?:/|$)", run.get("details_url") or "")
        if not identity or (not run.get("started_at") and run["status"] == "completed"):
            return remote
        identities[name] = identity
    for name in remote["failed"]:
        run = latest[name]
        if not run.get("started_at") or datetime.fromisoformat(run["started_at"]) < datetime.fromisoformat(jobs[name]["started"]):
            stale = True
            run_id = identities[name][1]
            if run["status"] == "completed" and run_id not in refreshed:
                gh_ok(["run", "rerun", run_id, "--repo", repo], error="main checks refresh failed")
                refreshed.add(run_id)
    if stale:
        return {**remote, "result": "pending", "pending": ["main checks refresh"]}
    inherited = []
    steps_checks = {}
    for name in remote["failed"]:
        if latest[name]["conclusion"] != "failure":
            return remote
        pr_job = gh_json(["api", f"repos/{repo}/actions/jobs/{jobs[name]['job']}"], error="PR job lookup failed")
        main_job = gh_json(["api", f"repos/{repo}/actions/jobs/{identities[name][2]}"], error="main job lookup failed")
        failed = {step["name"] for step in pr_job["steps"]
                  if step.get("conclusion") not in ("success", "skipped", "neutral")}
        main_failed = {step["name"] for step in main_job["steps"]
                       if step.get("conclusion") not in ("success", "skipped", "neutral")}
        if not failed or not failed <= main_failed:
            return remote
        inherited.append({"check": name, "steps": sorted(failed), "main_sha": main_sha})
        for step in sorted(failed):
            steps_checks.setdefault(step, []).append(name)
    issues = gh_json(["issue", "list", "--repo", repo, "--state", "all", "--limit", "1000000",
                      "--json", "number,state,body"], error="main checks issue lookup failed")
    logs = {}
    for step, names in steps_checks.items():
        marker = f"<!-- lokay main check: {step} -->"
        matches = [row for row in issues if marker in (row.get("body") or "").splitlines()]
        if any(row["state"] == "OPEN" for row in matches):
            continue
        if matches:
            number = min(int(row["number"]) for row in matches)
            gh_ok(["issue", "reopen", str(number), "--repo", repo], error="main checks issue reopen failed")
            continue
        tails = []
        for name in names:
            run_id = identities[name][1]
            if run_id not in logs:
                logs[run_id] = gh_ok(["run", "view", run_id, "--repo", repo, "--log-failed"],
                                     error="main checks log lookup failed")[-3000:]
            tails.append(f"{name}:\n{logs[run_id]}")
        body = (f"{marker}\n\nMain: {main_sha}\nChecks: {', '.join(names)}\n\n"
                + "\n\n".join(tails)
                + "\n\nThe fix belongs on main (for example a dependency bump); PRs that do not touch this step are not blocked by it.")
        gh_ok(["issue", "create", "--repo", repo, "--title", f'Main: GitHub checks fail on step "{step}"',
               "--body", fit_body(body)], error="main checks issue create failed")
    return {**remote, "result": "inherited", "inherited": inherited}


def checks_table(checks) -> str:
    def cell(value):
        return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")[:1000]

    def check_cells(row):
        if isinstance(row, CheckResult):
            return row.name, row.status, row.reason
        status = row.get("status") or ("unknown" if row["pass"] is None else "pass" if row["pass"] else "fail")
        return row["name"], status, row["reason"]

    return "| name | status | reason |\n| --- | --- | --- |\n" + "\n".join(
        f"| {cell(name)} | {cell(status)} | {cell(reason)} |"
        for name, status, reason in map(check_cells, checks)
    ) + "\n\n"


def check_comment(repo: str, number: int, round_number: int, verdict: dict, ci: dict) -> dict:
    body = (f"### Lokay Check {round_number}\n"
            f"SHA: `{verdict['sha']}`\n\n"
            f"Wynik: **{verdict['result']}** · CI: **{ci.get('ci', ci['result'])}** · "
            f"tests: **{ci['result']}** · tested={str(ci.get('tested', False)).lower()}\n\n")
    if verdict.get("checks"):
        body += checks_table(verdict["checks"])
    body += "Uwagi i CI:\n```json\n" + dumps({
                "uwagi": verdict.get("uwagi", []), "notes": verdict.get("notes", []),
                "failed": ci.get("failed", []), "pending": ci.get("pending", []),
            }, ensure_ascii=False, indent=2) + "\n```"
    notes = [parsed for note in verdict.get("notes", [])
             if isinstance(parsed := parse_finding(note), Note) and parsed.pytanie]
    if notes:
        body += "\n\n## Uwagi bez konkretu\n" + "\n".join(
            f"- {note.pytanie}: {note.note}" for note in notes)
    out = gh_ok(["pr", "comment", str(number), "--repo", repo, "--body", fit_body(body)], error="Check comment failed")
    return {"result": "commented", "url": out.strip()}


def merge(repo: str, number: int, expected_head_sha: str) -> dict:
    code, out, err = _gh(
        ["pr", "merge", str(number), "--repo", repo, "--merge", "--match-head-commit", expected_head_sha,
         "--body", f"Lokay-Merge: {store.TICK}"]
    )
    if code != 0:
        blob = (err or out).lower()
        if "head branch was modified" in blob:
            return {"result": "sha_moved", "merge_sha": None}
        view_code, view_out, _ = _gh([
            "pr", "view", str(number), "--repo", repo, "--json", "headRefOid",
        ])
        if view_code == 0:
            head = json.loads(view_out).get("headRefOid")
            if head and head != expected_head_sha:
                return {"result": "sha_moved", "merge_sha": None}
        if "behind" in blob:
            return {"result": "behind", "merge_sha": None}
        if "not mergeable" in blob or "conflict" in blob:
            return {"result": "conflict", "merge_sha": None}
        raise RuntimeError(err.strip() or out.strip() or "merge failed")
    view = gh_json(["pr", "view", str(number), "--repo", repo, "--json", "mergeCommit"],
                   error="merge commit lookup failed", strip=False)
    sha = (view.get("mergeCommit") or {}).get("oid")
    if not sha:
        raise RuntimeError("merge commit missing")
    return {"result": "merged", "merge_sha": sha}

