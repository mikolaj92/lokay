"""Atomic reserve, spawn, publish, and activate transaction for one delivery child."""

from __future__ import annotations
import os, secrets, subprocess, sys, time
from pathlib import Path
from typing import Any
from lokay.proc.issue_delivery_process import _terminate_detached_process_group
from lokay.proc.issue_delivery_receipts import (
    _ACTIVATION_PROTOCOL,
    _discard_starting_receipt,
    issue_to_pr_log_path,
    write_issue_to_pr_receipt,
)
from lokay.proc.health_delegation import abandon_delegated_lease, issue_delegated_lease
from lokay.proc.repo_lock import acquire_repo_lock, repo_lock_dir, repo_lock_path
from lokay.preflight import health_lease_status


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
    parent_token = os.environ.get("LOKAY_HEALTH_LEASE", "")
    parent_path = os.environ.get("LOKAY_HEALTH_LEASE_PATH", "").strip()
    if not parent_token:
        return {
            "ok": False,
            "reason": "capability_missing",
            "error": "detached issue_to_pr requires a parent run capability",
            "repo": repo_name,
            "issue": issue_number,
        }
    healthy, reason = health_lease_status()
    if not healthy or not parent_path:
        return {
            "ok": False,
            "reason": "capability_invalid",
            "error": f"parent run capability is not usable ({reason})",
            "repo": repo_name,
            "issue": issue_number,
        }
    delegated = issue_delegated_lease(
        work_id=work_id, parent_path=parent_path, parent_token=parent_token
    )
    if delegated is None:
        return {
            "ok": False,
            "reason": "capability_invalid",
            "error": "cannot delegate health capability to issue_to_pr worker",
            "repo": repo_name,
            "issue": issue_number,
        }

    lock_path = repo_lock_path(repo_lock_dir(config_path).parent, repo_name)
    lock_handle = acquire_repo_lock(lock_path)
    if lock_handle is None:
        abandon_delegated_lease(delegated["path"], delegated["token"])
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
    env["LOKAY_HEALTH_LEASE"] = delegated["token"]
    env["LOKAY_HEALTH_LEASE_PATH"] = delegated["path"]
    env["LOKAY_HEALTH_LEASE_PARENT"] = parent_path
    env["LOKAY_DISABLE_HEALTH_LEASE_ISSUE"] = "1"
    env["LOKAY_WORK_ID"] = work_id
    if not env.get("LOKAY_PROCESS_HEAD"):
        from lokay.git_host_ff import snapshot_process_head

        snapshot_process_head(Path(root))
        if os.environ.get("LOKAY_PROCESS_HEAD"):
            env["LOKAY_PROCESS_HEAD"] = os.environ["LOKAY_PROCESS_HEAD"]

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
        abandon_delegated_lease(delegated['path'], delegated['token'])
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
        abandon_delegated_lease(delegated['path'], delegated['token'])
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
        abandon_delegated_lease(delegated['path'], delegated['token'])
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
        abandon_delegated_lease(delegated['path'], delegated['token'])
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
        abandon_delegated_lease(delegated['path'], delegated['token'])
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
        abandon_delegated_lease(delegated['path'], delegated['token'])
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

    from lokay.proc.health_delegation import _read_record, _write_record

    delegated_record = _read_record(Path(delegated["path"]))
    if delegated_record is not None:
        delegated_record["owner_pid"] = int(proc.pid)
        delegated_record["heartbeat_at"] = int(time.time())
        try:
            _write_record(Path(delegated["path"]), delegated_record)
        except OSError:
            pass

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
        "health_lease": delegated["path"],
    }
    try:
        receipt["receipt"] = str(write_issue_to_pr_receipt(receipt))
    except OSError as exc:
        os.close(read_fd)
        os.close(write_fd)
        terminated = _terminate_detached_process_group(proc)
        if terminated:
            _discard_starting_receipt(receipt_path, launch_id)
        abandon_delegated_lease(delegated['path'], delegated['token'])
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
        abandon_delegated_lease(delegated["path"], delegated["token"])
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
