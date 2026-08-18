"""Drive shipped umocnienia: lease restore, stall exclusions, self-repair gate, detach."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

from lokay.graph_run import normalize_path_result
from lokay.passkit import io as pass_io
from lokay.passkit.health import evaluate_mill_stop
from lokay.preflight import (
    acquire_run_lock,
    has_health_lease,
    reconcile_incident_ledger,
    require_healthy,
)
from lokay.proc.compute_health import run_compute_health
from lokay.proc.detach_issue_to_pr import detach_issue_to_pr, live_issue_to_pr_receipts
from lokay.proc.self_repair_activate import main as activate_main
from lokay.proc.self_repair_prepare import published_self_repair_commit
from lokay.recovery_history import observe_run, record_observation


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
            seen["env"] = kwargs.get("env") or {}
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


def test_detach_forwards_lease_path_for_fala_inherit(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("LOKAY_HEALTH_LEASE", "d" * 64)
    monkeypatch.delenv("LOKAY_HEALTH_LEASE_PATH", raising=False)
    seen = {}

    class FakePopen:
        def __init__(self, argv, **kwargs):
            seen["env"] = kwargs.get("env") or {}
            self.pid = 7

    detach_issue_to_pr(
        repo="mikolaj92/Fala",
        issue=1,
        config_path=None,
        popen=FakePopen,
    )
    env = seen["env"]
    assert env.get("LOKAY_HEALTH_LEASE") == "d" * 64
    assert env.get("LOKAY_HEALTH_LEASE_PATH") == str(tmp_path / ".lokay" / "health-lease")


def test_evaluate_mill_stop_host_updated_is_soft_stop():
    decision = evaluate_mill_stop(
        {"ok": False, "health": "host_updated", "reason": "host_updated", "progress": 0}
    )
    assert decision["stop"] is True
    assert decision["hard"] is False
    assert decision["health"] == "host_updated"


def test_host_updated_is_not_stall_fingerprint(tmp_path):
    state = tmp_path / "state.jsonl"
    state.write_text("", encoding="utf-8")
    row = observe_run(
        state_path=state,
        state_offset=0,
        mill={
            "ok": False,
            "health": "host_updated",
            "reason": "host_updated",
            "error": "host checkout updated; restart required before product work",
            "progress": 0,
        },
    )
    assert row["fingerprint"] is None


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


def _issue_to_pr_cmd(pid: int) -> str:
    if pid == os.getpid():
        return "python -m lokay.compose.issue_to_pr --live --repo mikolaj92/Fala --issue 164"
    return ""


def test_live_receipts_keep_only_alive_pids(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("lokay.proc.detach_issue_to_pr._pid_command", _issue_to_pr_cmd)
    cycle = tmp_path / ".lokay" / "cycle"
    cycle.mkdir(parents=True)
    (cycle / "mikolaj92__Fala-164.json").write_text(
        json.dumps({"pid": os.getpid(), "repo": "mikolaj92/Fala", "issue": 164, "log": "a"}),
        encoding="utf-8",
    )
    (cycle / "mikolaj92__Temida-1.json").write_text(
        json.dumps({"pid": 999_999_999, "repo": "mikolaj92/Temida", "issue": 1, "log": "b"}),
        encoding="utf-8",
    )
    (cycle / "noise.json").write_text(json.dumps({"ok": True}), encoding="utf-8")
    live = live_issue_to_pr_receipts()
    assert len(live) == 1
    assert live[0]["repo"] == "mikolaj92/Fala" and live[0]["issue"] == 164


def test_compute_health_counts_live_receipts_as_started(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("lokay.proc.detach_issue_to_pr._pid_command", _issue_to_pr_cmd)
    cycle = tmp_path / ".lokay" / "cycle"
    cycle.mkdir(parents=True)
    (cycle / "mikolaj92__Fala-164.json").write_text(
        json.dumps(
            {
                "ok": True,
                "pid": os.getpid(),
                "repo": "mikolaj92/Fala",
                "issue": 164,
                "log": str(tmp_path / "x.log"),
            }
        ),
        encoding="utf-8",
    )
    (cycle / "mikolaj92__Temida-1.json").write_text(
        json.dumps({"pid": 999_999_999, "repo": "mikolaj92/Temida", "issue": 1, "log": "dead"}),
        encoding="utf-8",
    )
    pass_dir = tmp_path / "pass"
    pass_dir.mkdir()
    pass_io.write_json(
        pass_io.begin_path(pass_dir),
        {
            "live": True,
            "mode": "live",
            "repos": ["mikolaj92/Fala", "mikolaj92/Temida"],
            "max_issue_to_pr_per_pass": 4,
            "executor_enabled": True,
            "merge_enabled": True,
            "planned": [],
            "stuck_path": "",
        },
    )
    pass_io.write_json(
        pass_io.working_path(pass_dir),
        {
            "actions": [],
            "progress": 0,
            "issue_to_pr_started": 0,
            "remaining_ready": 10,
            "remaining_inbox": 0,
            "remaining_prs": 0,
            "actionable_prs": 0,
            "manual_prs": 0,
            "prs_by_repo": {},
            "ready_by_repo": {},
            "inbox_by_repo": {},
        },
    )
    result = run_compute_health(pass_dir=str(pass_dir))
    tick = pass_io.read_json(pass_io.tick_path(pass_dir))
    assert result["ok"] is True
    assert tick["remaining"]["issue_to_pr_started"] == 1
    assert tick["health"] == "progress"
    assert tick["progress"] == 1
    assert tick["idle"] is False


def test_activate_descendant_of_recovery_keeps_published_push(tmp_path, monkeypatch, capsys):
    clone = tmp_path / "lokay"
    bare = tmp_path / "origin.git"
    clone.mkdir()
    subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)
    def git(*args: str) -> None:
        subprocess.run(["git", "-C", str(clone), *args], check=True, capture_output=True)

    git("init")
    git("config", "user.email", "t@t.example")
    git("config", "user.name", "t")
    (clone / "a.txt").write_text("one\n", encoding="utf-8")
    git("add", "a.txt")
    git("commit", "-m", "self-repair: cafebabe")
    recovery = subprocess.check_output(
        ["git", "-C", str(clone), "rev-parse", "HEAD"], text=True
    ).strip()
    (clone / "a.txt").write_text("two\n", encoding="utf-8")
    git("add", "a.txt")
    git("commit", "-m", "host_ff later")
    descendant = subprocess.check_output(
        ["git", "-C", str(clone), "rev-parse", "HEAD"], text=True
    ).strip()
    git("branch", "-M", "main")
    git("remote", "add", "origin", str(bare))
    git("push", "-u", "origin", "main")

    from lokay.proc import self_repair_activate as act

    monkeypatch.setattr(
        act,
        "load_cfg",
        lambda a: SimpleNamespace(
            active_repos=lambda: [SimpleNamespace(name="mikolaj92/lokay", clone_path=clone)]
        ),
    )
    monkeypatch.setattr(act, "mutations_allowed", lambda **k: True)
    code = activate_main(["--live", "--commit", recovery])
    assert code == 0
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["ok"] is True
    assert payload["published"] is True
    assert payload["commit"] == recovery
    head = subprocess.check_output(
        ["git", "-C", str(clone), "rev-parse", "HEAD"], text=True
    ).strip()
    assert head == descendant


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


def test_live_receipt_with_unreadable_command_stays_occupied(tmp_path, monkeypatch):
    """A live PID with an unavailable ps command is not proof that its child died."""
    monkeypatch.setenv("HOME", str(tmp_path))
    cycle = tmp_path / ".lokay" / "cycle"
    cycle.mkdir(parents=True)
    (cycle / "owner__repo-9.json").write_text(
        json.dumps({"pid": os.getpid(), "repo": "owner/repo", "issue": 9}),
        encoding="utf-8",
    )
    monkeypatch.setattr("lokay.proc.detach_issue_to_pr._pid_command", lambda _pid: "")

    assert live_issue_to_pr_receipts() == [
        {"pid": os.getpid(), "repo": "owner/repo", "issue": 9}
    ]


def test_unreadable_pid_liveness_probe_stays_occupied(monkeypatch):
    """An OS probe error is unknown rather than a safe basis to launch/reap."""
    from lokay.proc.detach_issue_to_pr import pid_is_alive

    monkeypatch.setattr(
        "lokay.proc.detach_issue_to_pr.os.kill",
        lambda _pid, _sig: (_ for _ in ()).throw(OSError("probe unavailable")),
    )
    assert pid_is_alive(123) is True

def test_detach_reserves_receipt_before_child_can_start(tmp_path, monkeypatch):
    """The pre-spawn receipt closes the next-pass reaper window."""
    import lokay.proc.detach_issue_to_pr as detach_mod

    monkeypatch.setenv("HOME", str(tmp_path))
    seen = {}

    class FakePopen:
        def __init__(self, argv, **kwargs):
            receipt = detach_mod.issue_to_pr_receipt_path("owner/repo", 9)
            seen["during_spawn"] = json.loads(receipt.read_text(encoding="utf-8"))
            self.pid = 4242

    out = detach_mod.detach_issue_to_pr(
        repo="owner/repo", issue=9, config_path=None, popen=FakePopen
    )

    assert seen["during_spawn"] == {
        "ok": True,
        "detached": False,
        "starting": True,
        "launch_id": seen["during_spawn"]["launch_id"],
        "repo": "owner/repo",
        "issue": 9,
        "log": out["log"],
    }
    assert detach_mod.live_issue_to_pr_receipts(pid_alive=lambda _pid: True) == [
        json.loads(Path(out["receipt"]).read_text())
    ]


def test_detach_refuses_to_spawn_without_durable_reservation(tmp_path, monkeypatch):
    """Receipt storage failure is not allowed to create an untracked child."""
    import lokay.proc.detach_issue_to_pr as detach_mod

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(
        detach_mod,
        "write_issue_to_pr_receipt",
        lambda _payload: (_ for _ in ()).throw(OSError("disk full")),
    )
    out = detach_mod.detach_issue_to_pr(
        repo="owner/repo",
        issue=9,
        config_path=None,
        popen=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not spawn")),
    )

    assert out["ok"] is False
    assert out["reason"] == "receipt_unavailable"
    assert out["repo"] == "owner/repo"


def test_starting_receipt_keeps_repo_occupied_without_pid(tmp_path, monkeypatch):
    """A durable pre-Popen reservation remains occupancy until final publication."""
    import lokay.proc.detach_issue_to_pr as detach_mod

    monkeypatch.setenv("HOME", str(tmp_path))
    path = detach_mod.issue_to_pr_receipt_path("owner/repo", 9)
    path.write_text(
        json.dumps(
            {
                "ok": True,
                "starting": True,
                "launch_id": "launch",
                "repo": "owner/repo",
                "issue": 9,
            }
        ),
        encoding="utf-8",
    )

    assert detach_mod.live_issue_to_pr_receipts() == [json.loads(path.read_text())]


def test_detach_keeps_reservation_when_final_receipt_fails(tmp_path, monkeypatch):
    """If post-spawn publication fails, the child is killed and its KEEP remains."""
    import lokay.proc.detach_issue_to_pr as detach_mod

    monkeypatch.setenv("HOME", str(tmp_path))
    original = detach_mod.write_issue_to_pr_receipt
    calls = 0

    def fail_final(payload):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("I/O error")
        return original(payload)

    class FakePopen:
        pid = 4242

    monkeypatch.setattr(detach_mod, "write_issue_to_pr_receipt", fail_final)
    monkeypatch.setattr(detach_mod, "_terminate_detached_process_group", lambda _proc: False)
    out = detach_mod.detach_issue_to_pr(
        repo="owner/repo", issue=9, config_path=None, popen=lambda *_a, **_k: FakePopen()
    )

    assert out["ok"] is False
    assert out["reason"] == "receipt_unavailable"
    assert out["cleanup_confirmed"] is False
    assert detach_mod.live_issue_to_pr_receipts()[0]["starting"] is True



def test_unreadable_receipt_state_is_detected(tmp_path, monkeypatch):
    """Malformed lifecycle JSON is process-state uncertainty, not an empty cycle."""
    import lokay.proc.detach_issue_to_pr as detach_mod

    monkeypatch.setenv("HOME", str(tmp_path))
    cycle = tmp_path / ".lokay" / "cycle"
    cycle.mkdir(parents=True)
    (cycle / "partial.json").write_text("{", encoding="utf-8")

    assert detach_mod.has_unreadable_issue_to_pr_receipts() is True


def test_detach_does_not_replace_an_existing_starting_reservation(tmp_path, monkeypatch):
    """A second dispatch cannot steal the first launch's durable K=1 reservation."""
    import lokay.proc.detach_issue_to_pr as detach_mod

    monkeypatch.setenv("HOME", str(tmp_path))
    path = detach_mod.issue_to_pr_receipt_path("owner/repo", 9)
    path.write_text(
        json.dumps(
            {
                "ok": True,
                "starting": True,
                "launch_id": "other-launch",
                "repo": "owner/repo",
                "issue": 9,
            }
        ),
        encoding="utf-8",
    )
    out = detach_mod.detach_issue_to_pr(
        repo="owner/repo",
        issue=9,
        config_path=None,
        popen=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not spawn")),
    )

    assert out["ok"] is False
    assert out["reason"] == "receipt_unavailable"
    assert json.loads(path.read_text())["launch_id"] == "other-launch"



def test_detach_replaces_a_dead_completed_receipt(tmp_path, monkeypatch):
    """Historical dead receipts do not permanently block a later attempt."""
    import lokay.proc.detach_issue_to_pr as detach_mod

    monkeypatch.setenv("HOME", str(tmp_path))
    path = detach_mod.issue_to_pr_receipt_path("owner/repo", 9)
    path.write_text(
        json.dumps({"pid": 999_999_999, "repo": "owner/repo", "issue": 9}),
        encoding="utf-8",
    )
    out = detach_mod.detach_issue_to_pr(
        repo="owner/repo",
        issue=9,
        config_path=None,
        popen=lambda *_args, **_kwargs: type("P", (), {"pid": 4242})(),
    )

    assert out["ok"] is True
    assert json.loads(path.read_text())["pid"] == 4242



def test_final_receipt_requires_its_own_reservation(tmp_path, monkeypatch):
    """A final PID receipt cannot overwrite another launch's reservation."""
    import lokay.proc.detach_issue_to_pr as detach_mod

    monkeypatch.setenv("HOME", str(tmp_path))
    path = detach_mod.issue_to_pr_receipt_path("owner/repo", 9)
    path.write_text(
        json.dumps(
            {
                "starting": True,
                "launch_id": "other-launch",
                "repo": "owner/repo",
                "issue": 9,
            }
        ),
        encoding="utf-8",
    )

    try:
        detach_mod.write_issue_to_pr_receipt(
            {
                "pid": 4242,
                "launch_id": "this-launch",
                "repo": "owner/repo",
                "issue": 9,
            }
        )
    except OSError as exc:
        assert "reservation ownership changed" in str(exc)
    else:
        raise AssertionError("final receipt must require the matching reservation")
    assert json.loads(path.read_text())["launch_id"] == "other-launch"



def test_detach_discards_its_reservation_only_after_confirmed_cleanup(tmp_path, monkeypatch):
    """A failed final publication leaves no child or stale reservation after reaping."""
    import lokay.proc.detach_issue_to_pr as detach_mod

    monkeypatch.setenv("HOME", str(tmp_path))
    original = detach_mod.write_issue_to_pr_receipt
    calls = 0
    seen = []

    def fail_final(payload):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("I/O error")
        return original(payload)

    class FakePopen:
        pid = 4242

    monkeypatch.setattr(detach_mod, "write_issue_to_pr_receipt", fail_final)
    monkeypatch.setattr(
        detach_mod,
        "_terminate_detached_process_group",
        lambda proc: seen.append(proc.pid) is None,
    )
    out = detach_mod.detach_issue_to_pr(
        repo="owner/repo", issue=9, config_path=None, popen=lambda *_a, **_k: FakePopen()
    )

    assert out["ok"] is False
    assert out["cleanup_confirmed"] is True
    assert seen == [4242]
    assert not detach_mod.issue_to_pr_receipt_path("owner/repo", 9).exists()
