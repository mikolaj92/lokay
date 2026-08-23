"""Atomic lifecycle receipt storage for detached issue delivery."""

from __future__ import annotations
import fcntl, json, os, secrets
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any
from lokay.proc.issue_delivery_process import (
    is_live_issue_to_pr_pid,
    coding_live_for_issue,
    pid_is_alive,
)

_ACTIVATION_PROTOCOL = "pipe-v1"


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


@contextmanager
def _receipt_write_lock(path: Path):
    """Serialize all transitions over the receipt name, not its inode."""
    lock_path = path.parent / ".issue-to-pr-receipts.lock"
    try:
        with lock_path.open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    except OSError as exc:
        raise OSError(f"cannot lock issue_to_pr receipts: {exc}") from exc


def _starting_receipt_state(payload: dict[str, Any]) -> str:
    """Return ``live``, ``orphaned``, or ``unknown`` without trusting absence.

    Only pipe-gated reservations can be reclaimed. Their child holds only the
    read end before activation, so launcher death closes the write end and
    makes it exit before it can start Fala or touch a worktree. Old
    reservations predate that guarantee and deliberately retain their lane.
    """
    if payload.get("activation") != _ACTIVATION_PROTOCOL:
        return "live"
    try:
        launcher_pid = int(payload["launcher_pid"])
    except (KeyError, TypeError, ValueError):
        return "unknown"
    if launcher_pid <= 0:
        return "unknown"
    return "live" if pid_is_alive(launcher_pid) else "orphaned"


def _write_starting_receipt(path: Path, payload: dict[str, Any]) -> Path:
    """Reserve a receipt name once, before any child may be spawned."""
    with _receipt_write_lock(path):
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            # Completed/dead PID receipts are historical and replaceable. A
            # reservation remains until its pipe-gated launcher is proven dead;
            # malformed/legacy state is deliberately not ownership evidence.
            try:
                previous = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise OSError(
                    f"cannot inspect existing issue_to_pr receipt: {exc}"
                ) from exc
            if not isinstance(previous, dict):
                raise OSError("existing issue_to_pr receipt is not an object")
            if previous.get("starting") is True:
                state = _starting_receipt_state(previous)
                if state != "orphaned":
                    detail = "still starting" if state == "live" else "state is unknown"
                    raise OSError(f"existing issue_to_pr receipt is {detail}")
            elif previous.get("pid") is not None:
                try:
                    previous_pid = int(previous["pid"])
                except (TypeError, ValueError):
                    raise OSError(
                        "existing issue_to_pr receipt has an invalid pid"
                    ) from None
                if is_live_issue_to_pr_pid(previous_pid):
                    raise OSError("existing issue_to_pr receipt is still live")
            else:
                raise OSError("existing issue_to_pr receipt has no pid")
            try:
                path.unlink()
            except OSError as exc:
                raise OSError(
                    f"cannot clear completed issue_to_pr receipt: {exc}"
                ) from exc
            try:
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError as exc:
                raise OSError(
                    "issue_to_pr reservation was claimed concurrently"
                ) from exc
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
        return _write_starting_receipt(path, payload)

    # Hold the stable sidecar lock through matching ownership verification and
    # replacement: replacing a path changes its inode, so receipt-file locking
    # would permit a second launcher to be overwritten between read and rename.
    launch_id = str(payload.get("launch_id") or "")
    with _receipt_write_lock(path):
        if launch_id:
            try:
                previous = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise OSError(
                    f"cannot inspect starting issue_to_pr receipt: {exc}"
                ) from exc
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
        with _receipt_write_lock(path):
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("launch_id") != launch_id:
                return False
            path.unlink()
    except (OSError, ValueError):
        return False
    return True
