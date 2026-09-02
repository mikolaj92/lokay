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
from lokay.proc.repo_lock import acquire_repo_lock, repo_lock_dir, repo_lock_path


def _close_lock(handle) -> None:
    if handle is None:
        return
    try:
        handle.close()
    except OSError:
        pass


def detach_issue_to_pr(
    *,
    repo: str,
    issue: int,
    config_path: str | None,
    popen=None,
) -> dict[str, Any]:
    """Detach only after a repo lock, durable receipt, and child activation barrier.

    The child blocks on a private pipe before it can run Fala. The repo flock is
    acquired here and inherited by the child for the complete coding slot. The
    parent closes its copy after spawn so process death of the worker releases
    the lock without PID guessing or unlinking the lock file.
    """
    repo_name = str(repo)
    issue_number = int(issue)
    work_id = f"{repo_name}#{issue_number}"
    lock_path = repo_lock_path(repo_lock_dir(config_path).parent, repo_name)
    lock_handle = acquire_repo_lock(lock_path)
    if lock_handle is None:
        return {
            "ok": False,
            "reason": "repo_lock_busy",
            "error": f"repository lock is held: {lock_path}",
            "repo": repo_name,
            "issue": issue_number,
            "repo_lock": str(lock_path),
        }

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
        "repo_lock": str(lock_path),
    }
    try:
        receipt_path = write_issue_to_pr_receipt(starting)
    except OSError as exc:
        _close_lock(lock_handle)
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
        _close_lock(lock_handle)
        return {
            "ok": False,
            "reason": "activation_unavailable",
            "error": f"cannot create issue_to_pr activation pipe: {exc}",
            "repo": repo_name,
            "issue": issue_number,
        }
    env["LOKAY_ISSUE_TO_PR_ACTIVATION_FD"] = str(read_fd)
    env["LOKAY_REPO_LOCK_FD"] = str(lock_handle.fileno())
    try:
        log_fh = log_path.open("ab")
    except OSError as exc:
        os.close(read_fd)
        os.close(write_fd)
        _discard_starting_receipt(receipt_path, launch_id)
        _close_lock(lock_handle)
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
        _close_lock(lock_handle)
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
            pass_fds=(read_fd, lock_handle.fileno()),
        )
    except OSError as exc:
        os.close(read_fd)
        os.close(write_fd)
        _discard_starting_receipt(receipt_path, launch_id)
        _close_lock(lock_handle)
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
        _close_lock(lock_handle)
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
        "repo_lock": str(lock_path),
    }
    try:
        receipt["receipt"] = str(write_issue_to_pr_receipt(receipt))
    except OSError as exc:
        os.close(read_fd)
        os.close(write_fd)
        terminated = _terminate_detached_process_group(proc)
        if terminated:
            _discard_starting_receipt(receipt_path, launch_id)
        _close_lock(lock_handle)
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
        terminated = _terminate_detached_process_group(proc)
        _close_lock(lock_handle)
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
        _close_lock(lock_handle)
    return receipt
