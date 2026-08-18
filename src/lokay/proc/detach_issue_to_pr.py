"""One job: detach a live issue_to_pr child and persist its receipt."""

from __future__ import annotations

import json
import os
import secrets
import signal
import subprocess
import sys
import time
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


def _write_starting_receipt(path: Path, payload: dict[str, Any]) -> Path:
    """Reserve a receipt name once, before any child may be spawned."""
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        # Normal completed/dead receipts remain as history and may be replaced
        # for a later attempt. Live, malformed, and pre-spawn reservations are
        # unknown ownership and must instead hold the lane.
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise OSError(f"cannot inspect existing issue_to_pr receipt: {exc}") from exc
        if not isinstance(previous, dict):
            raise OSError("existing issue_to_pr receipt is not an object")
        if previous.get("starting") is True:
            raise OSError("existing issue_to_pr receipt is still starting")
        if previous.get("pid") is not None:
            try:
                previous_pid = int(previous["pid"])
            except (TypeError, ValueError):
                raise OSError("existing issue_to_pr receipt has an invalid pid") from None
            if is_live_issue_to_pr_pid(previous_pid):
                raise OSError("existing issue_to_pr receipt is still live")
        try:
            path.unlink()
        except OSError as exc:
            raise OSError(f"cannot clear completed issue_to_pr receipt: {exc}") from exc
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as exc:
            raise OSError("issue_to_pr reservation was claimed concurrently") from exc
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
    except BaseException:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return path


def write_issue_to_pr_receipt(payload: dict[str, Any]) -> Path:
    """Atomically reserve or publish an issue-to-PR lifecycle receipt."""
    path = issue_to_pr_receipt_path(str(payload["repo"]), int(payload["issue"]))
    if payload.get("starting") is True:
        # O_EXCL closes two dispatchers' absent-name race. Until complete JSON
        # is visible, readers treat it as unknown and hold the lane.
        return _write_starting_receipt(path, payload)

    # Final publication is allowed to replace only this launch's durable
    # pre-spawn reservation; it can never overwrite another child.
    launch_id = str(payload.get("launch_id") or "")
    if launch_id:
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise OSError(f"cannot inspect starting issue_to_pr receipt: {exc}") from exc
        if not isinstance(previous, dict) or previous.get("launch_id") != launch_id:
            raise OSError("issue_to_pr reservation ownership changed")
    temp = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    try:
        with temp.open("x", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temp, path)
    except BaseException:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return path


def _discard_starting_receipt(path: Path, launch_id: str) -> bool:
    """Drop only this launch's reservation after its process group is gone."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("launch_id") != launch_id:
            return False
        path.unlink()
    except (OSError, ValueError):
        return False
    return True


def _terminate_detached_process_group(proc: Any, *, timeout_seconds: float = 5.0) -> bool:
    """Terminate and confirm a child started with ``start_new_session=True`` is gone."""
    try:
        pid = int(proc.pid)
    except (AttributeError, TypeError, ValueError):
        return False
    if pid <= 0:
        return False

    def gone() -> bool:
        try:
            os.killpg(pid, 0)
        except ProcessLookupError:
            return True
        except OSError:
            return False
        return False

    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    except OSError:
        return False
    deadline = time.monotonic() + max(0.0, timeout_seconds)
    while time.monotonic() < deadline:
        if gone():
            return True
        time.sleep(0.05)
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        return True
    except OSError:
        return False
    deadline = time.monotonic() + max(0.0, timeout_seconds)
    while time.monotonic() < deadline:
        if gone():
            return True
        time.sleep(0.05)
    return gone()


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
        # An indeterminate liveness probe must not make an existing detached
        # receipt disappear from occupancy or destructive-reap protection.
        return True
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
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return (done.stdout or "").strip()


def is_live_issue_to_pr_pid(pid: int) -> bool:
    if not pid_is_alive(pid):
        return False
    command = _pid_command(pid)
    # A live PID whose command cannot be read is unknown, not dead. Keep its
    # receipt as occupancy so neither dispatch nor stale-worktree reap can race
    # a coding child. A readable non-Lokay command still rejects PID reuse.
    if not command:
        return True
    return "lokay.compose.issue_to_pr" in command or "lokay-issue-to-pr" in command


def has_unreadable_issue_to_pr_receipts(cycle_dir: Path | None = None) -> bool:
    """Whether cycle receipt state is unknown and destructive work must pause."""
    root = Path(cycle_dir) if cycle_dir is not None else Path.home() / ".lokay" / "cycle"
    try:
        with os.scandir(root) as entries:
            paths = sorted(
                (Path(entry.path) for entry in entries if entry.name.endswith(".json")),
                key=lambda path: path.name,
            )
    except FileNotFoundError:
        return False
    except OSError:
        return True
    for path in paths:
        try:
            if not isinstance(json.loads(path.read_text(encoding="utf-8")), dict):
                return True
        except (OSError, ValueError):
            return True
    return False


def live_issue_to_pr_receipts(
    cycle_dir: Path | None = None,
    *,
    pid_alive=None,
) -> list[dict[str, Any]]:
    """Live or launching receipts that must keep a repo occupied."""
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
        if not data.get("repo") or data.get("issue") is None:
            continue
        # A durable reservation written before Popen is occupancy until it is
        # replaced by the PID receipt or explicitly cleaned up after no spawn.
        if data.get("starting") is True and data.get("launch_id"):
            live.append(data)
            continue
        if "pid" not in data:
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
    """Detach only after a durable reservation protects its future worktree."""
    spawn = popen or subprocess.Popen
    repo_name = str(repo)
    issue_number = int(issue)
    argv = [sys.executable, "-u", "-m", "lokay.compose.issue_to_pr"]
    if config_path:
        argv.extend(["--config", str(config_path)])
    argv.extend(["--live", "--repo", repo_name, "--issue", str(issue_number)])
    root = os.environ.get("LOKAY_ROOT") or str(Path.cwd())
    env = os.environ.copy()
    # Fala effectors inherit these keys; an empty PATH fails commit_all.
    if env.get("LOKAY_HEALTH_LEASE") and not env.get("LOKAY_HEALTH_LEASE_PATH"):
        env["LOKAY_HEALTH_LEASE_PATH"] = str(Path.home() / ".lokay" / "health-lease")

    log_path = issue_to_pr_log_path(repo_name, issue_number)
    launch_id = secrets.token_hex(16)
    starting = {
        "ok": True,
        "detached": False,
        "starting": True,
        "launch_id": launch_id,
        "repo": repo_name,
        "issue": issue_number,
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
        log_fh = log_path.open("ab")
    except OSError as exc:
        _discard_starting_receipt(receipt_path, launch_id)
        return {
            "ok": False,
            "reason": "log_unavailable",
            "error": f"cannot open issue_to_pr log: {exc}",
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
        )
    except OSError as exc:
        _discard_starting_receipt(receipt_path, launch_id)
        return {
            "ok": False,
            "reason": "spawn_failed",
            "error": f"cannot start issue_to_pr: {exc}",
            "repo": repo_name,
            "issue": issue_number,
        }
    finally:
        log_fh.close()

    receipt = {
        "ok": True,
        "detached": True,
        "pid": int(proc.pid),
        "repo": repo_name,
        "issue": issue_number,
        "log": str(log_path),
        "launch_id": launch_id,
    }
    try:
        receipt["receipt"] = str(write_issue_to_pr_receipt(receipt))
    except OSError as exc:
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
    return receipt
