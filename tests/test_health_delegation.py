"""Detached workers receive a scoped capability; they never mint a parent lease."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from lokay.preflight import acquire_run_lock, has_health_lease, issue_health_lease
from lokay.proc.issue_delivery_launch import detach_issue_to_pr


def _parent_lease(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("LOKAY_HEALTH_LEASE", raising=False)
    monkeypatch.delenv("LOKAY_HEALTH_LEASE_PATH", raising=False)
    monkeypatch.delenv("LOKAY_DISABLE_HEALTH_LEASE_ISSUE", raising=False)
    lock = tmp_path / ".lokay" / "lokay.lock"
    assert acquire_run_lock(lock)
    issue_health_lease(lock_path=lock)
    assert has_health_lease() is True
    return os.environ["LOKAY_HEALTH_LEASE"], Path(os.environ["LOKAY_HEALTH_LEASE_PATH"])


class _FakePopen:
    def __init__(self, argv, **kwargs):
        self.argv = argv
        self.kwargs = kwargs
        self.pid = 4242
        self.env = kwargs.get("env") or {}


def test_detach_without_parent_capability_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("LOKAY_HEALTH_LEASE", raising=False)
    monkeypatch.delenv("LOKAY_HEALTH_LEASE_PATH", raising=False)
    out = detach_issue_to_pr(
        repo="mikolaj92/lokay",
        issue=9,
        config_path=None,
        popen=lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("must not spawn")),
    )
    assert out["ok"] is False
    assert out["reason"] == "capability_missing"
    assert not (tmp_path / ".lokay" / "health-lease").exists()


def test_detach_with_invalid_parent_token_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("LOKAY_HEALTH_LEASE", "a" * 64)
    monkeypatch.setenv(
        "LOKAY_HEALTH_LEASE_PATH", str(tmp_path / ".lokay" / "health-lease")
    )
    out = detach_issue_to_pr(
        repo="mikolaj92/lokay",
        issue=9,
        config_path=None,
        popen=lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("must not spawn")),
    )
    assert out["ok"] is False
    assert out["reason"] == "capability_invalid"


def test_detach_delegates_scoped_capability_and_never_mints_parent(
    tmp_path, monkeypatch
):
    parent_token, parent_path = _parent_lease(tmp_path, monkeypatch)
    seen = {}

    def popen(argv, **kwargs):
        seen["env"] = kwargs.get("env") or {}
        return _FakePopen(argv, **kwargs)

    out = detach_issue_to_pr(
        repo="mikolaj92/lokay", issue=9, config_path=None, popen=popen
    )
    assert out["ok"] is True
    env = seen["env"]
    delegated = env.get("LOKAY_HEALTH_LEASE")
    delegated_path = Path(env["LOKAY_HEALTH_LEASE_PATH"])
    assert delegated and delegated != parent_token
    assert delegated_path != parent_path
    assert delegated_path.name.startswith("health-lease-work-")
    record = json.loads(delegated_path.read_text(encoding="ascii"))
    assert record["kind"] == "delegated"
    assert record["work_id"] == "mikolaj92/lokay#9"
    assert record["parent_path"] == str(parent_path)
    assert env.get("LOKAY_DISABLE_HEALTH_LEASE_ISSUE") == "1"
    parent = json.loads(parent_path.read_text(encoding="ascii"))
    assert parent.get("kind") != "delegated"
    assert os.environ["LOKAY_HEALTH_LEASE"] == parent_token


def test_direct_live_compose_without_capability_fails_closed(tmp_path, monkeypatch):
    from lokay.compose import issue_to_pr

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("LOKAY_HEALTH_LEASE", raising=False)
    monkeypatch.delenv("LOKAY_HEALTH_LEASE_PATH", raising=False)
    monkeypatch.setattr(issue_to_pr, "_await_detach_activation", lambda: True)
    monkeypatch.setattr(
        issue_to_pr,
        "run_path",
        lambda **_k: (_ for _ in ()).throw(AssertionError("must not run product")),
    )
    out = issue_to_pr.compose_issue_to_pr(
        config_path=None, repo="mikolaj92/lokay", issue_number=9, live=True
    )
    assert out["ok"] is False
    assert out["reason"] in {"capability_missing", "capability_invalid"}


def test_child_heartbeats_and_completes_delegated_work_unit(tmp_path, monkeypatch):
    from lokay.proc.health_delegation import (
        complete_delegated_lease,
        heartbeat_delegated_lease,
        issue_delegated_lease,
    )

    parent_token, parent_path = _parent_lease(tmp_path, monkeypatch)
    delegated = issue_delegated_lease(
        work_id="mikolaj92/lokay#9", parent_path=parent_path, parent_token=parent_token
    )
    assert delegated is not None
    monkeypatch.setenv("LOKAY_HEALTH_LEASE", delegated["token"])
    monkeypatch.setenv("LOKAY_HEALTH_LEASE_PATH", delegated["path"])
    first = json.loads(Path(delegated["path"]).read_text(encoding="ascii"))
    beat = heartbeat_delegated_lease()
    assert beat["ok"] is True
    updated = json.loads(Path(delegated["path"]).read_text(encoding="ascii"))
    assert updated["heartbeat_at"] >= first["issued_at"]
    assert updated["work_id"] == "mikolaj92/lokay#9"
    done = complete_delegated_lease()
    assert done["ok"] is True
    finished = json.loads(Path(delegated["path"]).read_text(encoding="ascii"))
    assert finished["completed_at"]
    assert finished["state"] == "completed"


def test_dead_delegated_lease_is_pruned_without_touching_parent(tmp_path, monkeypatch):
    from lokay.preflight import prune_stale_health_leases
    from lokay.proc.health_delegation import issue_delegated_lease

    parent_token, parent_path = _parent_lease(tmp_path, monkeypatch)
    delegated = issue_delegated_lease(
        work_id="mikolaj92/lokay#9", parent_path=parent_path, parent_token=parent_token
    )
    path = Path(delegated["path"])
    record = json.loads(path.read_text(encoding="ascii"))
    record["owner_pid"] = 999_999_999
    path.write_text(json.dumps(record), encoding="ascii")
    path.chmod(0o600)
    result = prune_stale_health_leases(tmp_path / ".lokay")
    assert not path.exists()
    assert parent_path.exists()
    assert result["removed"] >= 1
