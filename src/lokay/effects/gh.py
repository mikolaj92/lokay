from __future__ import annotations

from json import dumps

import json
import os
import re
import shutil
import subprocess
from collections.abc import Mapping
from pathlib import Path

from lokay.effects.pi import retry_sleep, run_process
from lokay.store import log_event
from lokay.safety import validate_argv
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
    args = list(args)
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
    for attempt in range(4):
        try:
            proc = run_process([gh_bin(), *args], env=env, timeout=60, **({"cwd": str(cwd)} if cwd is not None else {}))
        except subprocess.TimeoutExpired:
            if attempt == 3:
                raise
            reason = "gh timed out"
        else:
            match = re.search(
                r"Something went wrong while executing your query|\bHTTP\s+(?:502|503|504)\b|"
                r"\btimeout\b|\btimed out\b|\bconnection reset\b|\bECONNRESET\b",
                (proc.stdout or "") + "\n" + (proc.stderr or ""), re.IGNORECASE,
            )
            if proc.returncode == 0 or match is None or attempt == 3:
                return proc.returncode, proc.stdout or "", proc.stderr or ""
            reason = match[0]
        log_event("retry", call="gh", attempt=attempt + 1, reason=reason)
        retry_sleep(3 ** attempt)
    raise AssertionError("unreachable")


def open_issues(repo: str) -> list[dict]:
    code, out, err = _gh(
        ["issue", "list", "--repo", repo, "--state", "open", "--limit", "1000000", "--json", "number,createdAt,title,labels"]
    )
    if code != 0:
        raise RuntimeError(err.strip() or "issue list failed")
    rows = json.loads(out or "[]")
    return sorted(rows, key=lambda row: (row["createdAt"], int(row["number"])))


def open_pr_for(repo: str, branch: str) -> dict | None:
    code, out, err = _gh(
        ["pr", "list", "--repo", repo, "--head", branch, "--state", "open", "--json", "number,headRefOid,baseRefName"]
    )
    if code != 0:
        raise RuntimeError(err.strip() or "pr list failed")
    rows = json.loads(out or "[]")
    return rows[0] if rows else None


def pr_files(repo: str, number: int) -> list[str]:
    code, out, err = _gh(["api", "--paginate", f"repos/{repo}/pulls/{number}/files", "--jq", ".[].filename"])
    if code:
        raise RuntimeError(err.strip() or "PR files lookup failed")
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
    code, out, err = _gh(["pr", "edit", str(number), "--repo", repo, "--body", fit_body(marked)])
    if code != 0:
        raise RuntimeError(err.strip() or "pr edit failed")
    return {"result": "updated", "pr": number}


def pr_checks(repo: str, number: int, sha: str) -> dict:
    code, out, err = _gh(["pr", "view", str(number), "--repo", repo, "--json", "statusCheckRollup,headRefOid"])
    if code != 0:
        raise RuntimeError(err.strip() or "pr view failed")
    view = json.loads(out)
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
    failed = []
    failed_logs = {}
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
        return {"result": "red", "sha": sha, "failed": failed, "failed_logs": failed_logs}
    return {"result": "green", "sha": sha, "failed": []}


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
    code, out, err = _gh(["pr", "comment", str(number), "--repo", repo, "--body", fit_body(body)])
    if code != 0:
        raise RuntimeError(err.strip() or "Check comment failed")
    return {"result": "commented", "url": out.strip()}


def merge(repo: str, number: int, expected_head_sha: str) -> dict:
    code, out, err = _gh(
        ["pr", "merge", str(number), "--repo", repo, "--merge", "--match-head-commit", expected_head_sha]
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
    code, out, err = _gh(["pr", "view", str(number), "--repo", repo, "--json", "mergeCommit"])
    if code:
        raise RuntimeError(err or "merge commit lookup failed")
    sha = (json.loads(out).get("mergeCommit") or {}).get("oid")
    if not sha:
        raise RuntimeError("merge commit missing")
    return {"result": "merged", "merge_sha": sha}


def dashboard_request(*args):
    try:
        result = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        raise RuntimeError("gh timed out after 60s") from None
    except OSError:
        raise RuntimeError("gh could not start") from None
    if result.returncode:
        raise RuntimeError(f"gh {args[0]} failed (exit {result.returncode})")
    try:
        return json.loads(result.stdout)
    except ValueError:
        raise RuntimeError("gh returned invalid JSON") from None
