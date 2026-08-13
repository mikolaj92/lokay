"""One job: detach a live issue_to_pr child and persist its receipt."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def issue_to_pr_log_path(repo: str, number: int) -> Path:
    slug = str(repo).replace("/", "__")
    root = Path.home() / ".lokay" / "logs"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"issue-to-pr-{slug}-{int(number)}.log"


def issue_to_pr_receipt_path(repo: str, number: int) -> Path:
    slug = str(repo).replace("/", "__")
    root = Path.home() / ".lokay" / "cycle"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{slug}-{int(number)}.json"


def write_issue_to_pr_receipt(payload: dict[str, Any]) -> Path:
    path = issue_to_pr_receipt_path(str(payload["repo"]), int(payload["issue"]))
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def detach_issue_to_pr(
    *,
    repo: str,
    issue: int,
    config_path: str | None,
    popen=None,
) -> dict[str, Any]:
    """Spawn issue_to_pr in a new session; do not wait. One job: detach + receipt."""
    spawn = popen or subprocess.Popen
    argv = [sys.executable, "-m", "lokay.compose.issue_to_pr"]
    if config_path:
        argv.extend(["--config", str(config_path)])
    argv.extend(["--live", "--repo", str(repo), "--issue", str(int(issue))])
    root = os.environ.get("LOKAY_ROOT") or str(Path.cwd())
    log_path = issue_to_pr_log_path(repo, issue)
    log_fh = log_path.open("ab")
    try:
        proc = spawn(
            argv,
            cwd=root,
            start_new_session=True,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
        )
    finally:
        log_fh.close()
    receipt = {
        "ok": True,
        "detached": True,
        "pid": int(proc.pid),
        "repo": repo,
        "issue": int(issue),
        "log": str(log_path),
    }
    receipt["receipt"] = str(write_issue_to_pr_receipt(receipt))
    return receipt
