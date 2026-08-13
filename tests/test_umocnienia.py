"""Drive shipped umocnienia: lease restore, stall exclusions, self-repair gate, detach."""

from __future__ import annotations

import json
from pathlib import Path

from lokay.graph_run import normalize_path_result
from lokay.passkit.health import evaluate_mill_stop
from lokay.preflight import (
    acquire_run_lock,
    has_health_lease,
    reconcile_incident_ledger,
    require_healthy,
)
from lokay.proc.detach_issue_to_pr import detach_issue_to_pr
from lokay.proc.self_repair_activate import main as activate_main
from lokay.proc.self_repair_prepare import published_self_repair_commit
from lokay.recovery_history import observe_run, record_observation
from types import SimpleNamespace


def test_missing_lease_file_with_inherited_token_allows_mutate(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("LOKAY_HEALTH_LEASE", "b" * 64)
    assert acquire_run_lock(tmp_path / ".lokay" / "mill.lock")
    assert has_health_lease() is False
    require_healthy("config.yaml")
    assert has_health_lease() is True
    assert (tmp_path / ".lokay" / "health-lease").is_file()


def test_lease_unavailable_is_not_stall_fingerprint(tmp_path):
    state = tmp_path / "state.jsonl"
    state.write_text("", encoding="utf-8")
    row = observe_run(
        state_path=state,
        state_offset=0,
        mill={
            "ok": False,
            "health": "stall",
            "error": "preflight failed; live mutation blocked (lease=lease_unavailable_FileNotFoundError)",
            "progress": 0,
        },
    )
    assert row["fingerprint"] is None


def test_plateau_does_not_confirm_stall(tmp_path):
    state = tmp_path / "state.jsonl"
    state.write_text("", encoding="utf-8")
    path = tmp_path / "history.json"
    signal = None
    for _ in range(5):
        obs = observe_run(
            state_path=state,
            state_offset=0,
            mill={"ok": False, "health": "plateau", "error": "mill plateau", "progress": 8},
        )
        signal = record_observation(path, obs)
        assert obs["fingerprint"] is None
    assert signal is None


def test_normalize_healthy_self_repair_releases_gate():
    envelope = {
        "ok": True,
        "path_id": "self_repair",
        "fala": {
            "effector_results": {
                "self_repair_push_main": {
                    "id": "self_repair:self_repair_push_main",
                    "status": "succeeded",
                    "output": {"values": {"ok": True, "commit": "abc1234"}},
                },
                "self_repair_activate": {
                    "id": "self_repair:self_repair_activate",
                    "status": "succeeded",
                    "output": {"values": {"ok": True, "activated": True, "commit": "abc1234"}},
                },
                "self_repair_preflight": {
                    "id": "self_repair:self_repair_preflight",
                    "status": "succeeded",
                    "output": {
                        "values": {
                            "ok": True,
                            "validated": True,
                            "restart_required": True,
                            "commit": "abc1234",
                        }
                    },
                },
                "self_repair_close": {
                    "id": "self_repair:self_repair_close",
                    "status": "succeeded",
                    "output": {"values": {"ok": True, "closed": True}},
                },
            }
        },
    }
    out = normalize_path_result(envelope)
    assert out["ok"] is True
    assert out["gate_released"] is True
    assert out["restart_required"] is True
    assert out["commit"] == "abc1234"


def test_normalize_dirty_activate_keeps_published_push():
    envelope = {
        "ok": True,
        "path_id": "self_repair",
        "fala": {
            "effector_results": {
                "self_repair_push_main": {
                    "id": "self_repair:self_repair_push_main",
                    "status": "succeeded",
                    "output": {"values": {"ok": True, "commit": "fff1111"}},
                },
                "self_repair_activate": {
                    "id": "self_repair:self_repair_activate",
                    "status": "succeeded",
                    "output": {
                        "values": {
                            "ok": True,
                            "activated": False,
                            "published": True,
                            "reason": "dirty_tree",
                            "commit": "fff1111",
                        }
                    },
                },
            }
        },
    }
    out = normalize_path_result(envelope)
    assert out["ok"] is True
    assert out["reason"] == "published_push_kept_dirty_tree"
    assert out["commit"] == "fff1111"


def test_published_self_repair_commit_reads_git_log(tmp_path):
    class FakeRun:
        def run(self, spec, live=True):
            assert "log" in spec.argv
            assert any("self-repair: abc" in str(a) for a in spec.argv)
            return SimpleNamespace(returncode=0, stdout="cafebabe0123\n")

    sha = published_self_repair_commit(
        clone=tmp_path, fingerprint="abc", run=FakeRun()
    )
    assert sha == "cafebabe0123"


def test_detach_writes_receipt_and_log(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    seen = {}

    class FakePopen:
        def __init__(self, argv, **kwargs):
            seen["argv"] = argv
            seen["session"] = kwargs.get("start_new_session")
            self.pid = 4242

    out = detach_issue_to_pr(
        repo="mikolaj92/Fala",
        issue=164,
        config_path="/tmp/config.yaml",
        popen=FakePopen,
    )
    assert out["pid"] == 4242 and out["detached"] is True
    receipt = Path(out["receipt"])
    assert receipt.is_file()
    data = json.loads(receipt.read_text())
    assert data["issue"] == 164 and data["log"].endswith("issue-to-pr-mikolaj92__Fala-164.log")
    assert seen["session"] is True
    assert "lokay.compose.issue_to_pr" in seen["argv"]


def test_evaluate_mill_stop_plateau_is_not_progress_continue():
    decision = evaluate_mill_stop({"ok": True, "health": "plateau", "progress": 4})
    assert decision["stop"] is True
    assert decision["health"] == "plateau"


def test_reconcile_closes_github_closed_rows(tmp_path, monkeypatch):
    from lokay import preflight

    ledger = {
        "aaa": {
            "state": "open",
            "repo": "mikolaj92/lokay",
            "number": 120,
        }
    }
    monkeypatch.setattr(preflight, "_read_incident_ledger", lambda cfg: ledger)
    written = {}

    def fake_write(cfg, data):
        written.update(data)
        return tmp_path / "incidents.json"

    monkeypatch.setattr(preflight, "_write_incident_ledger", fake_write)

    class Done:
        returncode = 0
        stdout = '{"state":"CLOSED"}'

    monkeypatch.setattr(preflight.subprocess, "run", lambda *a, **k: Done())
    out = reconcile_incident_ledger(None)
    assert out["closed"] == 1
    assert written["aaa"]["state"] == "closed"


def test_preflight_finding_checks_are_independently_invokable():
    from lokay.preflight_checks import FINDING_CHECKS, check_required_environment

    assert "github_authentication" in FINDING_CHECKS
    env = check_required_environment(repaired=set())
    assert env["name"] == "required_environment"
    assert "ok" in env and "code" in env


def test_organ_routing_files_stay_small():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "src" / "lokay"
    organ = root / "organ"
    assert (root / "fala_organ.py").is_file()
    assert (root / "fala_organ.py").read_text().count("\n") < 400
    for path in organ.glob("*.py"):
        if path.name == "__init__.py":
            continue
        lines = path.read_text().count("\n")
        assert lines < 400, f"{path.name} grew to {lines} lines"


def test_activate_dirty_keeps_published_commit(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from lokay.proc import self_repair_activate as act

    clone = tmp_path / "lokay"
    clone.mkdir()
    monkeypatch.setattr(
        act,
        "load_cfg",
        lambda a: SimpleNamespace(active_repos=lambda: [SimpleNamespace(name="mikolaj92/lokay", clone_path=clone)]),
    )
    monkeypatch.setattr(act, "mutations_allowed", lambda **k: True)

    def fake_run(cmd, **kwargs):
        if "status" in cmd:
            return SimpleNamespace(returncode=0, stdout=" M repos.mikolaj92.yaml\n")
        if "merge-base" in cmd:
            return SimpleNamespace(returncode=0, stdout="")
        return SimpleNamespace(returncode=1, stdout="")

    monkeypatch.setattr(act.subprocess, "run", fake_run)
    code = activate_main(["--live", "--commit", "abc1234"])
    assert code == 0
