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


def pid_is_alive(pid: int) -> bool:
    if int(pid) <= 0:
        return False
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _pid_command(pid: int) -> str:
    try:
        done = subprocess.run(
            ["ps", "-p", str(int(pid)), "-o", "command="],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except OSError:
        return ""
    return (done.stdout or "").strip()


def is_live_issue_to_pr_pid(pid: int) -> bool:
    if not pid_is_alive(pid):
        return False
    command = _pid_command(pid)
    return "lokay.compose.issue_to_pr" in command or "lokay-issue-to-pr" in command


def live_issue_to_pr_receipts(
    cycle_dir: Path | None = None,
    *,
    pid_alive=None,
) -> list[dict[str, Any]]:
    """Receipts whose recorded pid is still a live issue_to_pr. Next pass must see in-flight work."""
    root = Path(cycle_dir) if cycle_dir is not None else Path.home() / ".lokay" / "cycle"
    check = pid_alive or is_live_issue_to_pr_pid
    if not root.is_dir():
        return []
    live: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        if "pid" not in data or not data.get("repo") or data.get("issue") is None:
            continue
        try:
            pid = int(data["pid"])
        except (TypeError, ValueError):
            continue
        if check(pid):
            live.append(data)
    return live


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
    env = os.environ.copy()
    # Fala effectors inherit these keys; an empty PATH fails commit_all.
    if env.get("LOKAY_HEALTH_LEASE") and not env.get("LOKAY_HEALTH_LEASE_PATH"):
        env["LOKAY_HEALTH_LEASE_PATH"] = str(Path.home() / ".lokay" / "health-lease")
    log_path = issue_to_pr_log_path(repo, issue)
    log_fh = log_path.open("ab")
    try:
        proc = spawn(
            argv,
            cwd=root,
            env=env,
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
