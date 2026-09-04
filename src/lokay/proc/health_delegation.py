"""Scoped health capability for one detached coding slot.

Only the lokay-lock owner mints the parent run capability. Launch copies a
delegated record for `{repo}#{issue}` and the worker never mints another
parent token. Heartbeat and completion update that record in place.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import stat
import time
from pathlib import Path
from typing import Any

from lokay.preflight import _lease_path, _safe_owned_path, health_lease_status


def _write_record(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(temp, flags, 0o600)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or (
            hasattr(os, "getuid") and st.st_uid != os.getuid()
        ):
            raise OSError("unsafe health lease temp file")
        os.write(fd, json.dumps(record, sort_keys=True).encode("ascii"))
        os.fsync(fd)
    finally:
        os.close(fd)
    try:
        os.replace(temp, path)
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass
    path.chmod(0o600)


def _read_record(path: Path) -> dict[str, Any] | None:
    try:
        record = json.loads(path.read_text(encoding="ascii"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    return record if isinstance(record, dict) else None


def _token_matches(record: dict[str, Any], token: str) -> bool:
    if len(token) != 64:
        return False
    try:
        return secrets.compare_digest(
            str(record["token_sha256"]),
            hashlib.sha256(token.encode("ascii")).hexdigest(),
        )
    except (KeyError, TypeError):
        return False


def issue_delegated_lease(
    *,
    work_id: str,
    parent_path: str | Path,
    parent_token: str,
) -> dict[str, str] | None:
    """Mint a work-scoped capability from a valid parent run capability."""
    parent = Path(parent_path)
    if not parent_token or not _safe_owned_path(parent.parent):
        return None
    healthy, _reason = health_lease_status()
    if not healthy:
        return None
    parent_record = _read_record(parent)
    if parent_record is None or not _token_matches(parent_record, parent_token):
        return None
    if parent_record.get("kind") == "delegated":
        return None
    token = secrets.token_hex(32)
    now = int(time.time())
    path = parent.with_name(
        f"health-lease-work-{os.getpid()}-{secrets.token_hex(8)}"
    )
    record = {
        "token_sha256": hashlib.sha256(token.encode("ascii")).hexdigest(),
        "owner_pid": os.getpid(),
        "lock_path": str(parent_record.get("lock_path") or ""),
        "issued_at": now,
        "expires_at": now + 7200,
        "heartbeat_at": now,
        "kind": "delegated",
        "state": "active",
        "work_id": str(work_id),
        "parent_path": str(parent),
    }
    try:
        _write_record(path, record)
    except OSError:
        return None
    return {"token": token, "path": str(path.absolute())}


def heartbeat_delegated_lease() -> dict[str, Any]:
    """Refresh the inherited delegated record without minting a parent token."""
    path = _lease_path()
    token = os.environ.get("LOKAY_HEALTH_LEASE", "")
    record = _read_record(path)
    if record is None or record.get("kind") != "delegated":
        return {"ok": True, "applied": False}
    if not _token_matches(record, token):
        return {"ok": False, "reason": "token_mismatch"}
    now = int(time.time())
    record["heartbeat_at"] = now
    record["owner_pid"] = os.getpid()
    record["expires_at"] = max(int(record.get("expires_at") or 0), now + 7200)
    record["state"] = str(record.get("state") or "active")
    try:
        _write_record(path, record)
    except OSError as exc:
        return {"ok": False, "reason": str(exc)}
    return {"ok": True, "applied": True, "work_id": record.get("work_id")}


def abandon_delegated_lease(path: str | Path, token: str) -> None:
    """Expire a delegated record that never became a live worker."""
    target = Path(path)
    record = _read_record(target)
    if record is None or record.get("kind") != "delegated":
        return
    if not _token_matches(record, token):
        return
    now = int(time.time())
    record["expires_at"] = now
    record["heartbeat_at"] = now
    record["state"] = "abandoned"
    try:
        _write_record(target, record)
    except OSError:
        pass


def complete_delegated_lease() -> dict[str, Any]:
    """Mark the inherited delegated work unit complete. Never unlink."""
    path = _lease_path()
    token = os.environ.get("LOKAY_HEALTH_LEASE", "")
    record = _read_record(path)
    if record is None or record.get("kind") != "delegated":
        return {"ok": True, "applied": False}
    if not _token_matches(record, token):
        return {"ok": False, "reason": "token_mismatch"}
    now = int(time.time())
    record["completed_at"] = now
    record["heartbeat_at"] = now
    record["state"] = "completed"
    record["owner_pid"] = os.getpid()
    try:
        _write_record(path, record)
    except OSError as exc:
        return {"ok": False, "reason": str(exc)}
    return {"ok": True, "applied": True, "work_id": record.get("work_id")}
