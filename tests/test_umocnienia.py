"""Drive shipped umocnienia: lease restore, stall exclusions, self-repair gate, detach."""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

from lokay.passkit import io as pass_io
from lokay.passkit.health import evaluate_mill_stop
from lokay.preflight import (
    acquire_run_lock,
    has_health_lease,
    reconcile_incident_ledger,
    require_healthy,
)
from lokay.proc.compute_health import run_compute_health
from lokay.proc.detach_issue_to_pr import (
    detach_issue_to_pr,
    issue_to_pr_receipt_path,
    live_issue_to_pr_receipts,
)
from lokay.proc.find_published_self_repair import find as find_published_self_repair
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
            mill={
                "ok": False,
                "health": "plateau",
                "error": "mill plateau",
                "progress": 8,
            },
        )
        signal = record_observation(path, obs)
        assert obs["fingerprint"] is None
    assert signal is None


def test_published_self_repair_commit_reads_git_log(tmp_path):
    class FakeRun:
        def run(self, spec, live=True):
            assert "log" in spec.argv
            assert any("self-repair: abc" in str(a) for a in spec.argv)
            return SimpleNamespace(returncode=0, stdout="cafebabe0123\n")

    out = find_published_self_repair(
        {"clone": str(tmp_path), "fingerprint": "abc"}, run=FakeRun()
    )
    assert out["commit"] == "cafebabe0123" and out["route"] == "published"


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
        repo="mikolaj92/lokay",
        issue=164,
        config_path="/tmp/config.yaml",
        popen=FakePopen,
    )
    assert out["pid"] == 4242 and out["detached"] is True
    receipt = Path(out["receipt"])
    assert receipt.is_file()
    data = json.loads(receipt.read_text())
    assert data["issue"] == 164 and data["log"].endswith(
        "issue-to-pr-mikolaj92__lokay-164.log"
    )
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
        repo="mikolaj92/lokay",
        issue=1,
        config_path=None,
        popen=FakePopen,
    )
    env = seen["env"]
    assert env.get("LOKAY_HEALTH_LEASE") == "d" * 64
    assert env.get("LOKAY_HEALTH_LEASE_PATH") == str(
        tmp_path / ".lokay" / "health-lease"
    )


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
    monkeypatch.setattr(
        "lokay.proc.issue_delivery_process._pid_command", _issue_to_pr_cmd
    )
    cycle = tmp_path / ".lokay" / "cycle"
    cycle.mkdir(parents=True)
    (cycle / "mikolaj92__Fala-164.json").write_text(
        json.dumps(
            {"pid": os.getpid(), "repo": "mikolaj92/Fala", "issue": 164, "log": "a"}
        ),
        encoding="utf-8",
    )
    (cycle / "mikolaj92__Temida-1.json").write_text(
        json.dumps(
            {"pid": 999_999_999, "repo": "mikolaj92/Temida", "issue": 1, "log": "b"}
        ),
        encoding="utf-8",
    )
    (cycle / "noise.json").write_text(json.dumps({"ok": True}), encoding="utf-8")
    live = live_issue_to_pr_receipts()
    assert len(live) == 1
    assert live[0]["repo"] == "mikolaj92/Fala" and live[0]["issue"] == 164


def test_reaped_plan_only_receipt_is_not_occupancy(tmp_path, monkeypatch):
    """#192: over-budget plan_only must drop the slot without waiting for pi exit."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(
        "lokay.proc.issue_delivery_process._pid_command", _issue_to_pr_cmd
    )
    monkeypatch.setattr(
        "lokay.proc.detach_issue_to_pr.coding_live_for_issue", lambda _issue: True
    )
    cycle = tmp_path / ".lokay" / "cycle"
    cycle.mkdir(parents=True)
    (cycle / "mikolaj92__lokay-192.json").write_text(
        json.dumps(
            {
                "ok": False,
                "pid": os.getpid(),
                "repo": "mikolaj92/lokay",
                "issue": 192,
                "reason": "over_budget",
                "reaped": True,
            }
        ),
        encoding="utf-8",
    )
    assert live_issue_to_pr_receipts() == []


def test_compute_health_counts_live_receipts_as_started(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(
        "lokay.proc.issue_delivery_process._pid_command", _issue_to_pr_cmd
    )
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
        json.dumps(
            {"pid": 999_999_999, "repo": "mikolaj92/Temida", "issue": 1, "log": "dead"}
        ),
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


def test_compute_health_by_repo_contains_only_survey_scope(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    repos = [f"owner/repo-{number}" for number in range(29)]
    survey_scope = [repos[2], repos[11], repos[23]]
    pass_dir = tmp_path / "pass"
    pass_dir.mkdir()
    pass_io.write_json(
        pass_io.begin_path(pass_dir),
        {
            "live": True,
            "mode": "live",
            "repos": repos,
            "survey_repos": survey_scope,
            "max_issue_to_pr_per_pass": 1,
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
            "prs_by_repo": {},
            "ready_by_repo": {},
            "inbox_by_repo": {},
        },
    )

    run_compute_health(pass_dir=str(pass_dir))

    tick = pass_io.read_json(pass_io.tick_path(pass_dir))
    assert [row["repo"] for row in tick["remaining"]["by_repo"]] == survey_scope


def test_live_receipt_with_unreadable_command_stays_occupied(tmp_path, monkeypatch):
    """A live PID with an unavailable ps command is not proof that its child died."""
    monkeypatch.setenv("HOME", str(tmp_path))
    cycle = tmp_path / ".lokay" / "cycle"
    cycle.mkdir(parents=True)
    (cycle / "owner__repo-9.json").write_text(
        json.dumps({"pid": os.getpid(), "repo": "mikolaj92/lokay", "issue": 9}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "lokay.proc.issue_delivery_process._pid_command", lambda _pid: ""
    )

    assert live_issue_to_pr_receipts() == [
        {"pid": os.getpid(), "repo": "mikolaj92/lokay", "issue": 9}
    ]


def test_unreadable_pid_liveness_probe_stays_occupied(monkeypatch):
    """An OS probe error is unknown rather than a safe basis to launch/reap."""
    from lokay.proc.detach_issue_to_pr import pid_is_alive

    monkeypatch.setattr(
        "lokay.proc.issue_delivery_process.os.kill",
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
            receipt = issue_to_pr_receipt_path("mikolaj92/lokay", 9)
            seen["during_spawn"] = json.loads(receipt.read_text(encoding="utf-8"))
            seen["pass_fds"] = kwargs.get("pass_fds")
            self.pid = 4242

    out = detach_mod.detach_issue_to_pr(
        repo="mikolaj92/lokay", issue=9, config_path=None, popen=FakePopen
    )

    assert seen["during_spawn"] == {
        "ok": True,
        "detached": False,
        "starting": True,
        "activation": "pipe-v1",
        "launch_id": seen["during_spawn"]["launch_id"],
        "launcher_pid": os.getpid(),
        "repo": "mikolaj92/lokay",
        "issue": 9,
        "log": out["log"],
    }
    assert seen["during_spawn"]["launcher_pid"] == os.getpid()
    assert seen["pass_fds"] and len(seen["pass_fds"]) == 1
    assert detach_mod.has_unreadable_issue_to_pr_receipts() is False
    assert detach_mod.live_issue_to_pr_receipts(pid_alive=lambda _pid: True) == [
        json.loads(Path(out["receipt"]).read_text())
    ]


def test_detach_refuses_to_spawn_without_durable_reservation(tmp_path, monkeypatch):
    """Receipt storage failure is not allowed to create an untracked child."""
    import lokay.proc.issue_delivery_launch as detach_mod

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(
        detach_mod,
        "write_issue_to_pr_receipt",
        lambda _payload: (_ for _ in ()).throw(OSError("disk full")),
    )
    out = detach_mod.detach_issue_to_pr(
        repo="mikolaj92/lokay",
        issue=9,
        config_path=None,
        popen=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("must not spawn")
        ),
    )

    assert out["ok"] is False
    assert out["reason"] == "receipt_unavailable"
    assert out["repo"] == "mikolaj92/lokay"


def test_starting_receipt_keeps_repo_occupied_without_pid(tmp_path, monkeypatch):
    """A durable pre-Popen reservation remains occupancy until final publication."""

    monkeypatch.setenv("HOME", str(tmp_path))
    path = issue_to_pr_receipt_path("mikolaj92/lokay", 9)
    path.write_text(
        json.dumps(
            {
                "ok": True,
                "starting": True,
                "launch_id": "launch",
                "repo": "mikolaj92/lokay",
                "issue": 9,
            }
        ),
        encoding="utf-8",
    )

    assert live_issue_to_pr_receipts() == [json.loads(path.read_text())]


def test_detach_keeps_reservation_when_final_receipt_fails(tmp_path, monkeypatch):
    """If post-spawn publication fails, the child is killed and its KEEP remains."""
    import lokay.proc.issue_delivery_launch as detach_mod

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
    monkeypatch.setattr(
        detach_mod, "_terminate_detached_process_group", lambda _proc: False
    )
    out = detach_mod.detach_issue_to_pr(
        repo="mikolaj92/lokay",
        issue=9,
        config_path=None,
        popen=lambda *_a, **_k: FakePopen(),
    )

    assert out["ok"] is False
    assert out["reason"] == "receipt_unavailable"
    assert out["cleanup_confirmed"] is False
    assert live_issue_to_pr_receipts()[0]["starting"] is True


def test_unreadable_receipt_state_is_detected(tmp_path, monkeypatch):
    """Malformed lifecycle JSON is process-state uncertainty, not an empty cycle."""
    import lokay.proc.detach_issue_to_pr as detach_mod

    monkeypatch.setenv("HOME", str(tmp_path))
    cycle = tmp_path / ".lokay" / "cycle"
    cycle.mkdir(parents=True)
    (cycle / "partial.json").write_text("{", encoding="utf-8")

    assert detach_mod.has_unreadable_issue_to_pr_receipts() is True


def test_detach_does_not_replace_an_existing_starting_reservation(
    tmp_path, monkeypatch
):
    """A second dispatch cannot steal the first launch's durable K=1 reservation."""
    import lokay.proc.detach_issue_to_pr as detach_mod

    monkeypatch.setenv("HOME", str(tmp_path))
    path = issue_to_pr_receipt_path("mikolaj92/lokay", 9)
    path.write_text(
        json.dumps(
            {
                "ok": True,
                "starting": True,
                "launch_id": "other-launch",
                "repo": "mikolaj92/lokay",
                "issue": 9,
            }
        ),
        encoding="utf-8",
    )
    out = detach_mod.detach_issue_to_pr(
        repo="mikolaj92/lokay",
        issue=9,
        config_path=None,
        popen=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("must not spawn")
        ),
    )

    assert out["ok"] is False
    assert out["reason"] == "receipt_unavailable"
    assert json.loads(path.read_text())["launch_id"] == "other-launch"


def test_detach_replaces_a_dead_completed_receipt(tmp_path, monkeypatch):
    """Historical dead receipts do not permanently block a later attempt."""
    import lokay.proc.detach_issue_to_pr as detach_mod

    monkeypatch.setenv("HOME", str(tmp_path))
    path = issue_to_pr_receipt_path("mikolaj92/lokay", 9)
    path.write_text(
        json.dumps({"pid": 999_999_999, "repo": "mikolaj92/lokay", "issue": 9}),
        encoding="utf-8",
    )
    out = detach_mod.detach_issue_to_pr(
        repo="mikolaj92/lokay",
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
    path = issue_to_pr_receipt_path("mikolaj92/lokay", 9)
    path.write_text(
        json.dumps(
            {
                "starting": True,
                "launch_id": "other-launch",
                "repo": "mikolaj92/lokay",
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
                "repo": "mikolaj92/lokay",
                "issue": 9,
            }
        )
    except OSError as exc:
        assert "reservation ownership changed" in str(exc)
    else:
        raise AssertionError("final receipt must require the matching reservation")
    assert json.loads(path.read_text())["launch_id"] == "other-launch"


def test_detach_discards_its_reservation_only_after_confirmed_cleanup(
    tmp_path, monkeypatch
):
    """A failed final publication leaves no child or stale reservation after reaping."""
    import lokay.proc.issue_delivery_launch as detach_mod

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
        repo="mikolaj92/lokay",
        issue=9,
        config_path=None,
        popen=lambda *_a, **_k: FakePopen(),
    )

    assert out["ok"] is False
    assert out["cleanup_confirmed"] is True
    assert seen == [4242]
    assert not issue_to_pr_receipt_path("mikolaj92/lokay", 9).exists()


def test_dead_pipe_gated_starting_receipt_is_recoverable_without_live_worker(
    tmp_path, monkeypatch
):
    """A SIGKILL before final publication cannot wedge the issue forever.

    The child is pipe-gated, so a dead launcher has no path to start work;
    safely replacing its durable reservation lets the next dispatcher retry.
    """
    import lokay.proc.detach_issue_to_pr as detach_mod

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(detach_mod, "pid_is_alive", lambda _pid: False)
    path = issue_to_pr_receipt_path("mikolaj92/lokay", 9)
    path.write_text(
        json.dumps(
            {
                "ok": True,
                "detached": False,
                "starting": True,
                "activation": "pipe-v1",
                "launch_id": "dead-launch",
                "launcher_pid": 4242,
                "repo": "mikolaj92/lokay",
                "issue": 9,
            }
        ),
        encoding="utf-8",
    )

    assert live_issue_to_pr_receipts() == []
    assert detach_mod.has_unreadable_issue_to_pr_receipts() is False
    out = detach_mod.detach_issue_to_pr(
        repo="mikolaj92/lokay",
        issue=9,
        config_path=None,
        popen=lambda *_args, **_kwargs: type("P", (), {"pid": 4243})(),
    )
    assert out["ok"] is True
    assert json.loads(path.read_text())["pid"] == 4243


def test_legacy_starting_receipt_remains_live_not_reclaimable(tmp_path, monkeypatch):
    """Pre-barrier reservations lack proof that a hidden worker cannot exist."""
    import lokay.proc.detach_issue_to_pr as detach_mod

    monkeypatch.setenv("HOME", str(tmp_path))
    path = issue_to_pr_receipt_path("mikolaj92/lokay", 9)
    path.write_text(
        json.dumps(
            {
                "starting": True,
                "launch_id": "old-launch",
                "repo": "mikolaj92/lokay",
                "issue": 9,
            }
        ),
        encoding="utf-8",
    )

    assert live_issue_to_pr_receipts() == [json.loads(path.read_text())]
    out = detach_mod.detach_issue_to_pr(
        repo="mikolaj92/lokay",
        issue=9,
        config_path=None,
        popen=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("must not spawn")
        ),
    )
    assert out["reason"] == "receipt_unavailable"
    assert "still starting" in out["error"]


def test_pid_command_uses_wide_ps_to_avoid_macos_truncation(monkeypatch):
    """A nonempty 80-column Darwin command must not look like PID reuse."""
    import lokay.proc.detach_issue_to_pr as detach_mod

    seen = {}

    def fake_run(argv, **_kwargs):
        seen["argv"] = argv
        return SimpleNamespace(
            stdout="/long/python -u -m lokay.compose.issue_to_pr --repo owner/repo --issue 9\n"
        )

    monkeypatch.setattr("lokay.proc.issue_delivery_process.subprocess.run", fake_run)
    assert (
        detach_mod._pid_command(123)
        == "/long/python -u -m lokay.compose.issue_to_pr --repo owner/repo --issue 9"
    )
    assert seen["argv"] == ["ps", "-ww", "-p", "123", "-o", "command="]


def test_cycle_start_metric_receipt_is_not_lifecycle_uncertainty(tmp_path, monkeypatch):
    """The metric-only cycle_start schema coexists with detached receipts."""
    import lokay.proc.detach_issue_to_pr as detach_mod

    monkeypatch.setenv("HOME", str(tmp_path))
    cycle = tmp_path / ".lokay" / "cycle"
    cycle.mkdir(parents=True)
    (cycle / "owner__repo__9.json").write_text(
        json.dumps(
            {"repo": "owner/repo", "issue": 9, "started_ts": "2026-01-01T00:00:00Z"}
        ),
        encoding="utf-8",
    )
    assert detach_mod.has_unreadable_issue_to_pr_receipts() is False
    assert live_issue_to_pr_receipts() == []


def test_malformed_starting_receipt_is_global_lifecycle_uncertainty(
    tmp_path, monkeypatch
):
    """A partial reservation must not expose another repo's destructive lane."""
    import lokay.proc.detach_issue_to_pr as detach_mod

    monkeypatch.setenv("HOME", str(tmp_path))
    cycle = tmp_path / ".lokay" / "cycle"
    cycle.mkdir(parents=True)
    (cycle / "partial-start.json").write_text(
        json.dumps({"starting": True, "launch_id": "only-a-token"}),
        encoding="utf-8",
    )
    assert detach_mod.has_unreadable_issue_to_pr_receipts() is True
