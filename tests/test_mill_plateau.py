"""Mill must not burn pass budget on green-noop progress."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from lokay import preflight
from lokay.compose import mill as mill_mod


@pytest.fixture(autouse=True)
def _skip_leftover_closeout(monkeypatch):
    monkeypatch.setattr(
        mill_mod,
        "closeout_leftover_ready",
        lambda **_kwargs: {
            "ok": True,
            "labels_removed": False,
            "issue_to_pr_started": 0,
            "leftover_closed": 0,
        },
    )


def test_direct_live_mill_delegates_and_revokes_preflight_lease(monkeypatch, tmp_path):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        f"""
mode: live
repos:
  - name: a/b
    clone_path: {tmp_path}
worktrees:
  root: {tmp_path / "wt"}
state:
  path: {tmp_path / "state.jsonl"}
""",
        encoding="utf-8",
    )
    monkeypatch.delenv("LOKAY_HEALTH_LEASE", raising=False)
    calls: list[tuple[str, bool]] = []

    def preflight(config_path, *, remediate, issue_lease=False):
        calls.append(("preflight", issue_lease))
        monkeypatch.setenv("LOKAY_HEALTH_LEASE", "a" * 64)
        return {"ok": True}

    def factory_pass(**kwargs):
        calls.append(("factory", bool(os.environ.get("LOKAY_HEALTH_LEASE"))))
        return {"ok": True, "idle": True, "health": "idle", "progress": 0}

    def revoke():
        calls.append(("revoke", True))
        os.environ.pop("LOKAY_HEALTH_LEASE", None)

    monkeypatch.setattr(mill_mod, "run_preflight", preflight)
    monkeypatch.setattr(mill_mod, "health_lease_status", lambda: (True, "ok"))
    monkeypatch.setattr(mill_mod, "compose_factory_pass", factory_pass)
    monkeypatch.setattr(mill_mod, "revoke_health_lease", revoke)

    result = mill_mod.compose_mill(config_path=str(cfg_path), live=True)

    assert result["ok"] is True
    assert calls == [("preflight", True), ("factory", True), ("revoke", True)]


def test_direct_mills_with_distinct_state_paths_get_distinct_run_leases(
    monkeypatch, tmp_path
):
    config_paths = []
    state_dirs = [tmp_path / "first", tmp_path / "second"]
    for index, state_dir in enumerate(state_dirs):
        cfg_path = tmp_path / f"config-{index}.yaml"
        cfg_path.write_text(
            f"""
mode: live
repos:
  - name: a/b
    clone_path: {tmp_path}
worktrees:
  root: {tmp_path / f"wt-{index}"}
state:
  path: {state_dir / "events.jsonl"}
""",
            encoding="utf-8",
        )
        config_paths.append(cfg_path)

    lease_paths: list[Path] = []

    def run_preflight(config_path, *, remediate, issue_lease=False):
        lease_paths.append(Path(os.environ["LOKAY_HEALTH_LEASE_PATH"]))
        monkeypatch.setenv("LOKAY_HEALTH_LEASE", "a" * 64)
        return {"ok": True}

    def revoke():
        os.environ.pop("LOKAY_HEALTH_LEASE", None)
        os.environ.pop("LOKAY_HEALTH_LEASE_PATH", None)

    monkeypatch.delenv("LOKAY_HEALTH_LEASE", raising=False)
    monkeypatch.delenv("LOKAY_HEALTH_LEASE_PATH", raising=False)
    monkeypatch.setattr(mill_mod, "run_preflight", run_preflight)
    monkeypatch.setattr(mill_mod, "health_lease_status", lambda: (True, "ok"))
    monkeypatch.setattr(
        mill_mod,
        "compose_factory_pass",
        lambda **kwargs: {
            "ok": True,
            "idle": True,
            "health": "idle",
            "progress": 0,
        },
    )
    monkeypatch.setattr(mill_mod, "revoke_health_lease", revoke)

    for cfg_path in config_paths:
        assert mill_mod.compose_mill(config_path=str(cfg_path), live=True)["ok"] is True

    assert len(set(lease_paths)) == 2
    for lease_path, state_dir in zip(lease_paths, state_dirs, strict=True):
        assert lease_path.parent == state_dir
        assert lease_path.name.startswith("health-lease-")


def test_direct_live_mill_lease_validates_for_custom_state_path(monkeypatch, tmp_path):
    cfg_path = tmp_path / "config.yaml"
    state_dir = tmp_path / "custom" / "state"
    cfg_path.write_text(
        f"""
mode: live
repos:
  - name: a/b
    clone_path: {tmp_path}
executor:
  enabled: true
  command: omp
  args: ["-p", "{{prompt}}"]
worktrees:
  root: {tmp_path / "wt"}
state:
  path: {state_dir / "events.jsonl"}
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("LANG", "C.UTF-8")
    monkeypatch.setenv("LOKAY_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.delenv("LOKAY_DISABLE_HEALTH_LEASE_ISSUE", raising=False)
    monkeypatch.delenv("LOKAY_HEALTH_LEASE", raising=False)
    monkeypatch.delenv("LOKAY_HEALTH_LEASE_PATH", raising=False)
    from lokay import preflight_checks

    ok = type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()
    monkeypatch.setattr(preflight.shutil, "which", lambda command, **kwargs: f"/usr/bin/{command}")
    real_which = preflight_checks.shutil.which
    monkeypatch.setattr(
        preflight_checks.shutil,
        "which",
        lambda command, path=None, **kwargs: "/usr/bin/gh"
        if command == "gh"
        else real_which(command, path=path, **kwargs),
    )
    real_run = subprocess.run
    monkeypatch.setattr(
        preflight.subprocess,
        "run",
        lambda *args, **kwargs: ok
        if args[0][0] == "gh"
        else real_run(*args, **kwargs),
    )
    monkeypatch.setattr(preflight_checks.subprocess, "run", lambda *args, **kwargs: ok)
    observed: dict[str, object] = {}

    def factory_pass(**kwargs):
        child = real_run(
            [
                sys.executable,
                "-c",
                "from lokay.preflight import health_lease_status; "
                "raise SystemExit(0 if health_lease_status() == (True, 'ok') else 9)",
            ],
            env={**os.environ, "PYTHONPATH": str(Path(__file__).parents[1] / "src")},
            check=False,
        )
        observed["status"] = child.returncode
        observed["lease_path"] = os.environ["LOKAY_HEALTH_LEASE_PATH"]
        observed["record"] = json.loads(Path(observed["lease_path"]).read_text())
        return {"ok": True, "idle": True, "health": "idle", "progress": 0}

    monkeypatch.setattr(mill_mod, "compose_factory_pass", factory_pass)

    result = mill_mod.compose_mill(config_path=str(cfg_path), live=True)

    assert result["ok"] is True, result
    assert observed["status"] == 0
    assert Path(observed["lease_path"]).parent == state_dir
    assert Path(observed["lease_path"]).name.startswith("health-lease-")
    assert observed["record"]["lock_path"] == str((state_dir / "mill.lock").absolute())
    assert "LOKAY_HEALTH_LEASE" not in os.environ
    assert "LOKAY_HEALTH_LEASE_PATH" not in os.environ


def test_mill_plateau_stops_when_remaining_unchanged(monkeypatch, tmp_path):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        f"""
mode: live
repos:
  - name: a/b
    clone_path: {tmp_path}
executor:
  enabled: true
  agent: grok
  command: grok
  args: ["{{prompt}}"]
merge:
  enabled: true
  require_checks: false
worktrees:
  root: {tmp_path / "wt"}
state:
  path: {tmp_path / "state.jsonl"}
""",
        encoding="utf-8",
    )
    remaining = {
        "inbox": 2,
        "ready": 0,
        "open_ai_prs": 1,
        "mergeable_green": 0,
        "needs_repair": 0,
        "no_checks_blocked": 1,
        "merge_conflicts": 0,
        "survey_errors": 0,
    }
    calls = {"n": 0}

    def fake_tick(*, config_path=None, live=False):
        calls["n"] += 1
        return {
            "ok": True,
            "idle": False,
            "health": "progress",
            "progress": 2,
            "remaining": dict(remaining),
        }

    monkeypatch.setattr(mill_mod, "run_preflight", lambda *a, **kw: {"ok": True})
    monkeypatch.setattr(mill_mod, "compose_factory_pass", fake_tick)
    out = mill_mod.compose_mill(config_path=str(cfg_path), live=True, max_passes=8)
    assert out["ok"] is False
    assert out["health"] == "plateau"
    # first pass records baseline, second pass detects plateau
    assert calls["n"] == 2
    assert out["passes"] == 2


@pytest.mark.parametrize("in_flight_signal", ["started", "occupied"])
def test_mill_waits_when_ready_is_unchanged_during_issue_to_pr(
    monkeypatch, tmp_path, in_flight_signal
):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        f"""
mode: live
repos:
  - name: a/b
    clone_path: {tmp_path}
executor:
  enabled: true
  command: worker
  args: ["{{prompt}}"]
worktrees:
  root: {tmp_path / "wt"}
state:
  path: {tmp_path / "state.jsonl"}
""",
        encoding="utf-8",
    )
    remaining = {
        "inbox": 0,
        "ready": 1,
        "open_ai_prs": 0,
        "issue_to_pr_started": int(in_flight_signal == "started"),
        "by_repo": [
            {
                "repo": "a/b",
                "ready": 1,
                "occupied": in_flight_signal == "occupied",
            }
        ],
    }
    calls = {"n": 0}

    def fake_tick(**kwargs):
        calls["n"] += 1
        return {
            "ok": True,
            "idle": False,
            "health": "progress",
            "progress": 1,
            "remaining": remaining,
        }

    monkeypatch.setattr(mill_mod, "run_preflight", lambda *a, **kw: {"ok": True})
    monkeypatch.setattr(mill_mod, "compose_factory_pass", fake_tick)

    out = mill_mod.compose_mill(config_path=str(cfg_path), live=True, max_passes=8)

    assert out["ok"] is True
    assert out["health"] == "waiting"
    assert out["last"]["health"] == "waiting"
    assert out["last"]["progress"] == 0
    assert out["passes"] == calls["n"] == 2


def test_mill_stops_after_first_idle_health_pass(monkeypatch, tmp_path):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        f"""
mode: live
repos:
  - name: a/b
    clone_path: {tmp_path}
worktrees:
  root: {tmp_path / "wt"}
state:
  path: {tmp_path / "state.jsonl"}
""",
        encoding="utf-8",
    )
    calls = {"n": 0}
    idle_tick = {
        "ok": True,
        "idle": False,
        "health": "idle",
        "progress": 0,
        "remaining": {"ready": 0},
    }

    def fake_tick(**kwargs):
        calls["n"] += 1
        return idle_tick

    monkeypatch.setattr(mill_mod, "run_preflight", lambda *a, **kw: {"ok": True})
    monkeypatch.setattr(mill_mod, "compose_factory_pass", fake_tick)

    out = mill_mod.compose_mill(config_path=str(cfg_path), live=True, max_passes=8)

    assert out["ok"] is True
    assert out["idle"] is True
    assert out["health"] == "idle"
    assert out["passes"] == calls["n"] == 1
    assert out["last"] == idle_tick


def test_mill_propagates_failed_parent_pass(monkeypatch, tmp_path):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        f"""
mode: live
repos:
  - name: a/b
    clone_path: {tmp_path}
worktrees:
  root: {tmp_path / "wt"}
state:
  path: {tmp_path / "state.jsonl"}
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(mill_mod, "run_preflight", lambda *a, **kw: {"ok": True})
    monkeypatch.setattr(
        mill_mod,
        "compose_factory_pass",
        lambda **kwargs: {
            "ok": False,
            "error": {"code": "adapter_failed", "message": "child failed"},
        },
    )

    out = mill_mod.compose_mill(config_path=str(cfg_path), live=True)

    assert out["ok"] is False
    assert out["health"] == "failed"
    assert out["last"]["error"]["message"] == "child failed"


def test_mill_stops_truthfully_after_non_progress_repair_attempt(monkeypatch, tmp_path):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        f"""
mode: live
repos:
  - name: a/b
    clone_path: {tmp_path}
executor:
  enabled: true
  command: true
  args: ["{{prompt}}"]
merge:
  enabled: true
worktrees:
  root: {tmp_path / "wt"}
state:
  path: {tmp_path / "state.jsonl"}
""",
        encoding="utf-8",
    )
    calls = {"n": 0}

    def fake_tick(*, config_path=None, live=False):
        calls["n"] += 1
        return {
            "ok": False,
            "idle": False,
            "health": "stall",
            "progress": 0,
            "remaining": {
                "inbox": 0,
                "ready": 0,
                "open_ai_prs": 1,
                "mergeable_green": 0,
                "needs_repair": 1,
                "no_checks_blocked": 0,
                "merge_conflicts": 0,
                "survey_errors": 0,
            },
            "actions": [{"step": "pr_repair", "ok": True, "pushed": True}],
        }

    monkeypatch.setattr(mill_mod, "run_preflight", lambda *a, **kw: {"ok": True})
    monkeypatch.setattr(mill_mod, "compose_factory_pass", fake_tick)
    out = mill_mod.compose_mill(config_path=str(cfg_path), live=True, max_passes=8)

    assert out["ok"] is False
    assert out["health"] == "stall"
    assert "plateau" not in out["error"]
    assert out["progress"] == 0
    assert out["passes"] == calls["n"] == 1
