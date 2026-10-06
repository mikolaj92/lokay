import hashlib
import json
import os
import time

import pytest

from lokay import preflight


@pytest.mark.parametrize("failure", ["lease_lstat", "lease_read", "bound_lock_open"])
def test_missing_filesystem_boundary_is_identifiable_without_leaking_capability(tmp_path, monkeypatch, failure):
    token = "a" * 64
    lease = tmp_path / "lease"
    lock = tmp_path / "missing" / "owner.lock"
    now = int(time.time())
    lease.write_text(json.dumps({"owner_pid": os.getpid(), "lock_path": str(lock),
                                "issued_at": now, "expires_at": now + 7200,
                                "token_sha256": hashlib.sha256(token.encode()).hexdigest()}))
    lease.chmod(0o600)
    monkeypatch.setenv("LOKAY_HEALTH_LEASE", token)
    monkeypatch.setenv("LOKAY_HEALTH_LEASE_PATH", str(lease))
    if failure == "lease_lstat":
        lease.unlink()
    elif failure == "lease_read":
        original = type(lease).read_text

        def disappeared(path, *args, **kwargs):
            if path == lease:
                raise FileNotFoundError("sensitive filesystem detail")
            return original(path, *args, **kwargs)

        monkeypatch.setattr(type(lease), "read_text", disappeared)
    healthy, reason = preflight.health_lease_status()
    assert healthy is False
    assert reason == f"lease_unavailable_FileNotFoundError:{failure}"
    assert token not in reason and str(tmp_path) not in reason
