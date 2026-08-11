"""Mill must not burn pass budget on green-noop progress."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from lokay import preflight
from lokay.compose import mill as mill_mod


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
    monkeypatch.setattr(preflight.shutil, "which", lambda command, **kwargs: f"/usr/bin/{command}")
    real_run = subprocess.run
    monkeypatch.setattr(
        preflight.subprocess,
        "run",
        lambda *args, **kwargs: type("Completed", (), {"returncode": 0})()
        if args[0][0] == "gh"
        else real_run(*args, **kwargs),
    )
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
        observed["record"] = json.loads(
            Path(os.environ["LOKAY_HEALTH_LEASE_PATH"]).read_text()
        )
        return {"ok": True, "idle": True, "health": "idle", "progress": 0}

    monkeypatch.setattr(mill_mod, "compose_factory_pass", factory_pass)

    result = mill_mod.compose_mill(config_path=str(cfg_path), live=True)

    assert result["ok"] is True, result
    assert observed["status"] == 0
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
