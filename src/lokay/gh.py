from __future__ import annotations

import json
import os
import shutil
from collections.abc import Mapping
from pathlib import Path

from lokay.run import run_process
from lokay.safety import validate_argv

ORIGIN = "lokay"
GH_CANDIDATES = (
    Path.home() / ".local/share/mise/installs/gh/2.102.0/gh_2.102.0_macOS_arm64/bin/gh",
    Path("/opt/homebrew/bin/gh"),
    Path("/usr/local/bin/gh"),
)


def gh_bin() -> str:
    found = shutil.which("gh")
    if found:
        return found
    for path in GH_CANDIDATES:
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    return "gh"


def _gh(args: list[str], env: Mapping[str, str] | None = None) -> tuple[int, str, str]:
    validate_argv(["gh", *args])
    proc = run_process([gh_bin(), *args], env=env, timeout=60)
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def issues_with_label(repo: str, label: str = "lokaj") -> list[dict]:
    code, out, err = _gh(
        ["issue", "list", "--repo", repo, "--label", label, "--state", "open", "--json", "number,createdAt,title"]
    )
    if code != 0:
        raise RuntimeError(err.strip() or "issue list failed")
    rows = json.loads(out or "[]")
    return sorted(rows, key=lambda row: row["createdAt"])


def open_pr_for(repo: str, branch: str) -> dict | None:
    code, out, err = _gh(
        ["pr", "list", "--repo", repo, "--head", branch, "--state", "open", "--json", "number,headRefOid"]
    )
    if code != 0:
        raise RuntimeError(err.strip() or "pr list failed")
    rows = json.loads(out or "[]")
    return rows[0] if rows else None


def pr_create(repo: str, branch: str, title: str, body: str, issue: int) -> dict:
    marked = body.rstrip() + f"\n\nCloses #{issue}\n\nOpened by {ORIGIN}.\n"
    code, out, err = _gh(
        ["pr", "create", "--repo", repo, "--head", branch, "--title", title, "--body", marked]
    )
    if code != 0:
        raise RuntimeError(err.strip() or "pr create failed")
    return {"result": "pr_open", "url": out.strip()}


def pr_checks(repo: str, number: int, sha: str) -> dict:
    code, out, err = _gh(["pr", "view", str(number), "--repo", repo, "--json", "statusCheckRollup,headRefOid"])
    if code != 0:
        raise RuntimeError(err.strip() or "pr view failed")
    view = json.loads(out)
    if view.get("headRefOid") != sha:
        return {"result": "sha_moved", "sha": view.get("headRefOid") or ""}
    rollup = view.get("statusCheckRollup") or []
    failed = [item.get("name") for item in rollup if item.get("conclusion") not in (None, "SUCCESS", "NEUTRAL", "SKIPPED")]
    pending = [item.get("name") for item in rollup if item.get("conclusion") is None and item.get("status") != "COMPLETED"]
    if failed or pending:
        return {"result": "red", "sha": sha, "failed": failed, "pending": pending}
    return {"result": "green", "sha": sha, "failed": []}


def comment_upsert(repo: str, number: int, marker: str, body: str) -> dict:
    code, out, err = _gh(["pr", "view", str(number), "--repo", repo, "--json", "comments"])
    if code != 0:
        raise RuntimeError(err.strip() or "comments failed")
    comments = json.loads(out).get("comments") or []
    text = f"<!-- {marker} -->\n{body}"
    for comment in comments:
        if marker in (comment.get("body") or ""):
            cid = comment["id"]
            code, out, err = _gh(["api", "-X", "PATCH", f"repos/{repo}/issues/comments/{cid}", "-f", f"body={text}"])
            if code != 0:
                raise RuntimeError(err.strip() or "comment patch failed")
            return {"result": "updated", "id": cid}
    code, out, err = _gh(["pr", "comment", str(number), "--repo", repo, "--body", text])
    if code != 0:
        raise RuntimeError(err.strip() or "comment failed")
    return {"result": "created", "url": out.strip()}


def merge(repo: str, number: int, expected_head_sha: str) -> dict:
    code, out, err = _gh(
        ["pr", "merge", str(number), "--repo", repo, "--merge", "--match-head-commit", expected_head_sha]
    )
    if code != 0:
        blob = (err or out).lower()
        if "match" in blob or "head" in blob or "not mergeable" in blob:
            return {"result": "sha_moved", "merge_sha": None}
        raise RuntimeError(err.strip() or out.strip() or "merge failed")
    return {"result": "merged", "merge_sha": expected_head_sha}
