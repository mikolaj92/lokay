"""Fala-only composition for issue → PR."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from typing import Any

from lokay.config import load_config
from lokay.envelope import emit_exit
from lokay.graph_run import run_path
from lokay.proc._common import add_config_live
from lokay.state import append_event


def _await_detach_activation() -> bool:
    """Block a detached child until its parent durably publishes its PID."""
    raw = os.environ.get("LOKAY_ISSUE_TO_PR_ACTIVATION_FD")
    if raw is None:
        return True
    fd: int | None = None
    try:
        fd = int(raw)
        if fd < 0:
            return False
        return os.read(fd, 1) == b"1"
    except (OSError, ValueError):
        return False
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass


def _command_json(args: list[str]) -> Any | None:
    """Return command JSON, or None when a survey is unavailable."""
    try:
        completed = subprocess.run(
            args,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return json.loads(completed.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return None


def _head_has_on_goal_src(repo: str, issue_number: int) -> bool:
    """Recognize a resumed issue branch without mistaking main for delivered."""
    try:
        current = subprocess.run(
            ["git", "branch", "--show-current"], check=True, capture_output=True,
            text=True, timeout=10,
        ).stdout.strip()
        remote = subprocess.run(
            ["git", "remote", "get-url", "origin"], check=True, capture_output=True,
            text=True, timeout=10,
        ).stdout.strip().removesuffix(".git")
        files = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
            check=True, capture_output=True, text=True, timeout=10,
        ).stdout.splitlines()
    except (OSError, subprocess.SubprocessError):
        return False
    remote_matches = remote.endswith(f"github.com/{repo}") or remote.endswith(f":{repo}")
    issue_branch = re.search(rf"(?:^|[/_-]){issue_number}(?:$|[/_-])", current) is not None
    return remote_matches and issue_branch and any(path.startswith("src/") for path in files)


def _delivery_stop_reason(repo: str, issue_number: int) -> str | None:
    issue = _command_json(
        ["gh", "issue", "view", str(issue_number), "--repo", repo, "--json", "state"]
    )
    if isinstance(issue, dict) and str(issue.get("state", "")).upper() == "CLOSED":
        return "issue_closed"

    prs = _command_json(
        [
            "gh", "pr", "list", "--repo", repo, "--state", "all", "--limit", "100",
            "--json", "body,state,mergedAt",
        ]
    )
    closes_issue = re.compile(
        rf"\b(?:fixes|closes|resolves)\s+#{issue_number}\b",
        re.IGNORECASE,
    )
    for pr in prs if isinstance(prs, list) else []:
        if not isinstance(pr, dict) or not closes_issue.search(str(pr.get("body") or "")):
            continue
        if str(pr.get("state", "")).upper() == "OPEN" or pr.get("mergedAt"):
            return "delivery_pr_exists"

    if _head_has_on_goal_src(repo, issue_number):
        return "head_has_on_goal_src"
    return None


def compose_issue_to_pr(
    *,
    config_path: str | None,
    repo: str,
    issue_number: int,
    live: bool,
    incident_fingerprint: str = "",
    package_path: str | None = None,
) -> dict:
    if not _await_detach_activation():
        return {"ok": False, "reason": "detachment_not_activated"}
    if live and load_config(config_path).mode != "live":
        return {"ok": False, "error": "refusing live compose while config mode is not live"}

    if live and (stop_reason := _delivery_stop_reason(repo, issue_number)):
        return {
            "ok": True,
            "kind": "issue_to_pr",
            "engine": "fala",
            "planned": False,
            "stopped": True,
            "reason": stop_reason,
            "repo": repo,
            "issue": issue_number,
        }

    result = run_path(
        path_id="issue_to_pr", repo=repo, issue=issue_number,
        config_path=config_path, live=live, package_path=package_path,
        extra_inputs={"incident_fingerprint": incident_fingerprint, "keep_issue_open": bool(incident_fingerprint)},
    )
    result.update(kind="issue_to_pr", engine="fala", planned=not live)
    try:
        append_event(load_config(config_path).state_path, result)
    except Exception:
        pass
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-issue-to-pr")
    add_config_live(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--issue", required=True, type=int)
    args = p.parse_args(argv)
    return emit_exit(compose_issue_to_pr(config_path=args.config, repo=args.repo, issue_number=args.issue, live=bool(args.live)))


if __name__ == "__main__":
    raise SystemExit(main())
