"""Atomic reserve, spawn, publish, and activate transaction for one delivery child."""

from __future__ import annotations
import os, secrets, subprocess, sys
from pathlib import Path
from typing import Any
from lokay.proc.issue_delivery_process import _terminate_detached_process_group
from lokay.proc.issue_delivery_receipts import (
    _ACTIVATION_PROTOCOL,
    _discard_starting_receipt,
    issue_to_pr_log_path,
    write_issue_to_pr_receipt,
)


def detach_issue_to_pr(
    *,
    repo: str,
    issue: int,
    config_path: str | None,
    popen=None,
) -> dict[str, Any]:
    """Detach only after a durable receipt and child activation barrier.

    The child blocks on a private pipe before it can run Fala. If this parent
    dies after ``Popen`` but before final publication, its write end closes and
    the child exits without touching a worktree. That makes a later recovery
    of the pre-spawn reservation safe rather than a second-worker race.
    """
    repo_name = str(repo)
    issue_number = int(issue)
    work_id = f"{repo_name}#{issue_number}"

    spawn = popen or subprocess.Popen
    argv = [sys.executable, "-u", "-m", "lokay.compose.issue_to_pr"]
    if config_path:
        argv.extend(["--config", str(config_path)])
    argv.extend(["--live", "--repo", repo_name, "--issue", str(issue_number)])
    root = os.environ.get("LOKAY_ROOT") or str(Path.cwd())
    env = os.environ.copy()
    root = env.get("LOKAY_ROOT") or str(Path.cwd())
    if not env.get("LOKAY_PROCESS_HEAD"):
        from lokay.git_host_ff import snapshot_process_head

        snapshot_process_head(Path(root))
        if os.environ.get("LOKAY_PROCESS_HEAD"):
            env["LOKAY_PROCESS_HEAD"] = os.environ["LOKAY_PROCESS_HEAD"]
    if not env.get("LOKAY_HEALTH_LEASE"):
        from lokay.preflight import issue_health_lease

        issue_health_lease()
        for key in ("LOKAY_HEALTH_LEASE", "LOKAY_HEALTH_LEASE_PATH"):
            if os.environ.get(key):
                env[key] = os.environ[key]
    if env.get("LOKAY_HEALTH_LEASE") and not env.get("LOKAY_HEALTH_LEASE_PATH"):
        env["LOKAY_HEALTH_LEASE_PATH"] = str(Path.home() / ".lokay" / "health-lease")

    log_path = issue_to_pr_log_path(repo_name, issue_number)
    launch_id = secrets.token_hex(16)
    starting = {
        "ok": True,
        "detached": False,
        "starting": True,
        "activation": _ACTIVATION_PROTOCOL,
        "launch_id": launch_id,
        "launcher_pid": os.getpid(),
        "repo": repo_name,
        "issue": issue_number,
        "work_id": work_id,
        "state": "starting",
        "log": str(log_path),
    }
    try:
        receipt_path = write_issue_to_pr_receipt(starting)
    except OSError as exc:
        return {
            "ok": False,
            "reason": "receipt_unavailable",
            "error": f"cannot reserve issue_to_pr receipt: {exc}",
            "repo": repo_name,
            "issue": issue_number,
        }

    try:
        read_fd, write_fd = os.pipe()
    except OSError as exc:
        _discard_starting_receipt(receipt_path, launch_id)
        return {
            "ok": False,
            "reason": "activation_unavailable",
            "error": f"cannot create issue_to_pr activation pipe: {exc}",
            "repo": repo_name,
            "issue": issue_number,
        }
    env["LOKAY_ISSUE_TO_PR_ACTIVATION_FD"] = str(read_fd)
    try:
        log_fh = log_path.open("ab")
    except OSError as exc:
        os.close(read_fd)
        os.close(write_fd)
        _discard_starting_receipt(receipt_path, launch_id)
        return {
            "ok": False,
            "reason": "log_unavailable",
            "error": f"cannot open issue_to_pr log: {exc}",
            "repo": repo_name,
            "issue": issue_number,
        }
    try:
        log_fh.write(f"started issue={issue_number} pid-pending\n".encode("ascii"))
        log_fh.flush()
    except OSError as exc:
        log_fh.close()
        os.close(read_fd)
        os.close(write_fd)
        _discard_starting_receipt(receipt_path, launch_id)
        return {
            "ok": False,
            "reason": "log_unavailable",
            "error": f"cannot write issue_to_pr log: {exc}",
            "repo": repo_name,
            "issue": issue_number,
        }
    try:
        proc = spawn(
            argv,
            cwd=root,
            env=env,
            start_new_session=True,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            pass_fds=(read_fd,),
        )
    except OSError as exc:
        os.close(read_fd)
        os.close(write_fd)
        _discard_starting_receipt(receipt_path, launch_id)
        return {
            "ok": False,
            "reason": "spawn_failed",
            "error": f"cannot start issue_to_pr: {exc}",
            "repo": repo_name,
            "issue": issue_number,
        }
    try:
        log_fh.write(f"pid={int(proc.pid)}\n".encode("ascii"))
        log_fh.flush()
    except OSError as exc:
        log_fh.close()
        os.close(read_fd)
        os.close(write_fd)
        terminated = _terminate_detached_process_group(proc)
        if terminated:
            _discard_starting_receipt(receipt_path, launch_id)
        return {
            "ok": False,
            "reason": "log_unavailable",
            "error": f"cannot write issue_to_pr pid to log: {exc}",
            "repo": repo_name,
            "issue": issue_number,
            "pid": int(proc.pid),
            "cleanup_confirmed": terminated,
        }
    finally:
        log_fh.close()

    receipt = {
        "ok": True,
        "detached": True,
        "pid": int(proc.pid),
        "repo": repo_name,
        "issue": issue_number,
        "work_id": work_id,
        "state": "implementing",
        "log": str(log_path),
        "launch_id": launch_id,
    }
    try:
        receipt["receipt"] = str(write_issue_to_pr_receipt(receipt))
    except OSError as exc:
        os.close(read_fd)
        os.close(write_fd)
        terminated = _terminate_detached_process_group(proc)
        if terminated:
            _discard_starting_receipt(receipt_path, launch_id)
        return {
            "ok": False,
            "reason": "receipt_unavailable",
            "error": f"cannot publish issue_to_pr receipt: {exc}",
            "repo": repo_name,
            "issue": issue_number,
            "pid": int(proc.pid),
            "cleanup_confirmed": terminated,
        }
    try:
        os.write(write_fd, b"1")
    except OSError as exc:
        # The receipt is durable but a child that never read activation cannot
        # work; terminate conservatively and leave its final historical receipt.
        terminated = _terminate_detached_process_group(proc)
        return {
            "ok": False,
            "reason": "activation_unavailable",
            "error": f"cannot release issue_to_pr child: {exc}",
            "repo": repo_name,
            "issue": issue_number,
            "pid": int(proc.pid),
            "cleanup_confirmed": terminated,
        }
    finally:
        os.close(read_fd)
        os.close(write_fd)
    return receipt
