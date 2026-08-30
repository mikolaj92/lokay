import json
import os
import subprocess
from pathlib import Path

import pytest

from lokay.compose import daemon_cycle
from lokay.compose.daemon_cycle import finalize_daemon_payload
from lokay.envelope import process_exit_code
from lokay.proc import daemon


def _script() -> Path:
    return Path(__file__).parents[1] / "scripts" / "lokay-mill-daemon.sh"


def test_daemon_is_os_only():
    script = _script().read_text(encoding="utf-8")
    assert "idle_skip" not in script
    assert "host_ff_already_current" not in script
    assert "plistlib" not in script
    assert "import plistlib" not in script
    assert "uv run lokay-host-ff" not in script
    assert "uv run lokay-repos" not in script
    assert "uv run lokay-mill" not in script
    assert "preflight-bootstrap-incidents.log" in script
    assert 'export PYTHONPATH="${ROOT}/src' in script
    assert "mill_lock_busy" in script
    assert "lock_busy" in script
    assert "uv run lokay-daemon" in script
    assert "LOKAY_PASS_CEILING_SECONDS" in script
    assert "stop_lock_owner" in script
    assert "start_new_session" in script
    assert "pass_ceiling" in script
    assert "bootstrap_incident" in script
    assert "write_host_plist" in script
    assert "plutil" in script
    assert "recent_empty_survey" not in script
    assert "GraphQL" not in script
    assert "ThreadPoolExecutor" not in script
    assert "| tee " in script


def test_daemon_handles_missing_home_and_bounds_bootstrap_outbox():
    script = _script().read_text()
    assert 'HOME="${HOME:-${TMPDIR:-/tmp}/lokay-${UID:-unknown}}"' in script
    assert 'wc -c < "${OUTBOX}"' in script
    assert "-ge 65536" in script
    assert ': > "${OUTBOX}"' in script


def _fake_uv(local_bin: Path) -> Path:
    uv = local_bin / "uv"
    uv.write_text(
        "#!/bin/sh\n"
        "log=${LOKAY_UV_ARGV_LOG:-}\n"
        'if [ -n "$log" ]; then printf \'%s\\n\' "$*" >> "$log"; fi\n'
        'case "$*" in\n'
        "  *lokay-daemon*)\n"
        '    if [ -n "$LOKAY_UV_DAEMON_MARKER" ]; then : > "$LOKAY_UV_DAEMON_MARKER"; fi\n'
        '    while [ -n "$LOKAY_UV_DAEMON_GATE" ] && [ ! -e "$LOKAY_UV_DAEMON_GATE" ]; do sleep 0.01; done\n'
        "    ;;\n"
        "esac\n"
        'if [ "$LOKAY_UV_DAEMON_FAIL" = 1 ]; then echo fail >&2; exit 1; fi\n'
        'if [ "$1" = run ] && [ "$2" = lokay-daemon ]; then\n'
        '  printf \'%s\\n\' "$(command -v pi)" "$PATH"\n'
        '  if [ -n "$LOKAY_UV_ENVELOPE" ]; then printf \'%s\\n\' "$LOKAY_UV_ENVELOPE"; else\n'
        '    printf \'%s\\n\' \'{"ok":false,"health":"progress","progress":1}\'\n'
        "  fi\n"
        "  exit 0\n"
        "fi\n"
        "exit 64\n",
        encoding="utf-8",
    )
    uv.chmod(0o755)
    return uv


def _run_daemon(
    tmp_path: Path,
    extra_env: dict[str, str] | None = None,
    *,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
):
    root = tmp_path / "repo"
    local_bin = tmp_path / ".local" / "bin"
    root.mkdir(exist_ok=True)
    local_bin.mkdir(parents=True, exist_ok=True)
    (root / "config.yaml").touch()
    (local_bin / "pi").write_text("#!/bin/sh\nexit 0\n")
    (local_bin / "pi").chmod(0o755)
    _fake_uv(local_bin)
    env = {
        "HOME": str(tmp_path),
        "LOKAY_ROOT": str(root),
        "LOKAY_CONFIG": str(root / "config.yaml"),
        "PATH": "/usr/bin:/bin",
        "LOKAY_UV_ARGV_LOG": str(tmp_path / "uv-argv.log"),
    }
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["/bin/bash", str(_script())],
        env=env,
        stdout=stdout,
        stderr=stderr,
        text=True,
        check=False,
    )


def test_daemon_always_execs_lokay_daemon(tmp_path):
    completed = _run_daemon(tmp_path)
    assert completed.returncode == 0, completed.stderr
    calls = (tmp_path / "uv-argv.log").read_text(encoding="utf-8").splitlines()
    assert any("lokay-daemon" in line for line in calls)
    assert all("lokay-host-ff" not in line for line in calls)
    logs = list((tmp_path / ".lokay" / "logs").glob("mill-*.log"))
    assert logs
    body = "\n".join(path.read_text(encoding="utf-8") for path in logs)
    assert "progress" in body


def test_idle_stamps_still_exec_lokay_daemon(tmp_path):
    lokay = tmp_path / ".lokay"
    lokay.mkdir()
    (lokay / "last-pass.json").write_text(
        json.dumps(
            {
                "health": "idle",
                "idle": True,
                "remaining": {"inbox": 0, "ready": 0, "open_ai_prs": 0},
            }
        ),
        encoding="utf-8",
    )
    (lokay / "factory-survey.stamp").write_text("1", encoding="utf-8")
    completed = _run_daemon(tmp_path)
    assert completed.returncode == 0, completed.stderr
    calls = (tmp_path / "uv-argv.log").read_text(encoding="utf-8").splitlines()
    assert any("lokay-daemon" in line for line in calls)


def test_busy_lock_skips_daemon(tmp_path):
    import fcntl

    lokay = tmp_path / ".lokay"
    lokay.mkdir()
    lock = lokay / "mill.lock"
    handle = lock.open("a+", encoding="utf-8")
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        completed = _run_daemon(tmp_path)
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()
    assert completed.returncode == 0, completed.stderr
    argv = tmp_path / "uv-argv.log"
    calls = argv.read_text(encoding="utf-8").splitlines() if argv.is_file() else []
    assert all("lokay-daemon" not in line for line in calls)
    assert "lock_busy" in completed.stdout


def test_missing_uv_writes_bootstrap_incident(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "config.yaml").touch()
    env = {
        "HOME": str(tmp_path),
        "LOKAY_ROOT": str(root),
        "LOKAY_CONFIG": str(root / "config.yaml"),
        "PATH": "/usr/bin:/bin",
    }
    completed = subprocess.run(
        ["/bin/bash", str(_script())],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 69
    incident = tmp_path / ".lokay" / "preflight-bootstrap-incidents.log"
    assert "uv_unavailable" in incident.read_text(encoding="utf-8")


def test_daemon_exec_failure_writes_incident(tmp_path):
    completed = _run_daemon(tmp_path, extra_env={"LOKAY_UV_DAEMON_FAIL": "1"})
    assert completed.returncode != 0
    incident = tmp_path / ".lokay" / "preflight-bootstrap-incidents.log"
    assert "daemon_exec" in incident.read_text(encoding="utf-8")


def test_latest_log_is_current_before_daemon_finishes(tmp_path):
    import threading
    import time

    logs = tmp_path / ".lokay" / "logs"
    logs.mkdir(parents=True)
    latest = logs / "mill-latest.log"
    latest.write_text('{"health":"pass_ceiling"}\n', encoding="utf-8")
    marker = tmp_path / "daemon-started"
    gate = tmp_path / "daemon-finish"
    result = {}

    thread = threading.Thread(
        target=lambda: result.setdefault(
            "completed",
            _run_daemon(
                tmp_path,
                extra_env={
                    "LOKAY_UV_DAEMON_MARKER": str(marker),
                    "LOKAY_UV_DAEMON_GATE": str(gate),
                },
            ),
        )
    )
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert marker.exists(), "lokay-daemon did not start"
        body = latest.read_text(encoding="utf-8")
        assert '"health":"current"' in body
        assert "pass_ceiling" not in body
    finally:
        gate.touch()
        thread.join(timeout=5)
    assert not thread.is_alive()
    assert result["completed"].returncode == 0, result["completed"].stderr


def test_install_does_not_invent_a_missing_plist(tmp_path):
    plist = tmp_path / "Library" / "LaunchAgents" / "ai.mikolaj.lokay-test.plist"
    env = {
        "HOME": str(tmp_path),
        "PATH": "/usr/bin:/bin",
        "LOKAY_LAUNCHD_PLIST": str(plist),
        "LOKAY_LAUNCHD_LABEL": "ai.mikolaj.lokay-test",
    }
    completed = subprocess.run(
        ["/bin/bash", str(_script()), "--install"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert not plist.exists()


def test_install_rewrites_existing_plist_when_plutil_exists(tmp_path):
    import shutil

    if shutil.which("plutil") is None:
        pytest.skip("plutil not on this host")
    plist = tmp_path / "Library" / "LaunchAgents" / "ai.mikolaj.lokay-test.plist"
    plist.parent.mkdir(parents=True, exist_ok=True)
    plist.write_text(
        "<?xml version='1.0' encoding='UTF-8'?>\n"
        "<!DOCTYPE plist PUBLIC '-//Apple//DTD PLIST 1.0//EN' "
        "'http://www.apple.com/DTDs/PropertyList-1.0.dtd'>\n"
        "<plist version='1.0'><dict>"
        "<key>Label</key><string>ai.mikolaj.lokay-test</string>"
        "<key>StartInterval</key><integer>600</integer>"
        "</dict></plist>\n",
        encoding="utf-8",
    )
    env = {
        "HOME": str(tmp_path),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "LOKAY_LAUNCHD_PLIST": str(plist),
        "LOKAY_LAUNCHD_LABEL": "ai.mikolaj.lokay-test",
    }
    completed = subprocess.run(
        ["/bin/bash", str(_script()), "--install"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert plist.exists()


def _write_cfg(tmp_path, *, state_name: str = "state.jsonl") -> str:
    cfg = tmp_path / "config.yaml"
    state_dir = tmp_path / "lokay-state"
    state_dir.mkdir(parents=True, exist_ok=True)
    cfg.write_text(
        f"""
mode: dry-run
repos:
  - name: a/b
    clone_path: {tmp_path}
executor:
  enabled: false
  command: true
  args: ["{{prompt}}"]
state:
  path: {state_dir / state_name}
""",
        encoding="utf-8",
    )
    return str(cfg)


def test_process_exit_zero_when_pass_did_work():
    assert (
        process_exit_code(
            {"ok": False, "health": "host_updated", "reason": "host_updated"}
        )
        == 0
    )
    assert process_exit_code({"ok": False, "health": "progress", "progress": 2}) == 0
    assert (
        process_exit_code({"ok": False, "remaining": {"issue_to_pr_started": 1}}) == 0
    )
    assert (
        process_exit_code({"ok": False, "mill": {"health": "progress", "progress": 1}})
        == 0
    )
    assert process_exit_code({"ok": False, "health": "stall"}) == 1
    assert (
        process_exit_code(
            {"ok": False},
            last_pass={"health": "progress", "progress": 4},
        )
        == 0
    )
    assert (
        process_exit_code(
            {"ok": False, "health": "stall"},
            last_pass={"health": "progress", "progress": 4},
        )
        == 1
    )


def test_process_exit_zero_at_pass_ceiling():
    assert process_exit_code({"ok": False, "health": "pass_ceiling"}) == 0
    assert process_exit_code({"ok": False, "reason": "pass_ceiling"}) == 0
    assert process_exit_code({"ok": False}) == 1


def test_finalize_daemon_payload_lifts_progress_and_drops_fala():
    out = finalize_daemon_payload(
        {
            "ok": False,
            "error": "soft recovery",
            "fala": {"host": "x" * 1000, "processes": []},
            "mill": {
                "health": "progress",
                "progress": 3,
                "remaining": {"issue_to_pr_started": 1},
            },
        }
    )
    assert out["health"] == "progress"
    assert out["progress"] == 3
    assert out["remaining"]["issue_to_pr_started"] == 1
    assert "fala" not in out


def test_daemon_cycle_pass_ceiling_writes_receipt(monkeypatch, tmp_path):
    cfg = _write_cfg(tmp_path)
    receipt = tmp_path / "lokay-state" / "last-pass.json"
    stale = {"inbox": 0, "ready": 0, "by_repo": {"a/b": {"remaining_ready": 0}}}
    receipt.write_text(json.dumps({"remaining": stale}), encoding="utf-8")
    inflight = tmp_path / "lokay-state" / "factory-pass-1-deadbeef"
    inflight.mkdir()
    (inflight / "working.json").write_text(
        json.dumps(
            {
                "remaining_inbox": 4,
                "remaining_ready": 1,
                "inbox_issues_by_repo": {
                    "mikolaj92/Temida": [
                        {"number": 4972, "labels": ["enhancement"]},
                        {"number": 4973, "labels": ["bug"]},
                        {"number": 4969, "labels": ["work:ready"]},
                    ],
                    "mikolaj92/Fala": [{"number": 176, "labels": ["oil"]}],
                },
                "ready_by_repo": {
                    "mikolaj92/Temida": [{"number": 4968, "labels": ["ai:ready"]}]
                },
            }
        ),
        encoding="utf-8",
    )

    def wait_forever(**_kwargs):
        import time

        time.sleep(1)
        return {"ok": True}

    monkeypatch.setattr(daemon_cycle, "run_path", wait_forever)
    out = daemon_cycle.compose_daemon_cycle(
        config_path=cfg,
        pass_ceiling_seconds=0.02,
    )

    assert out["ok"] is False
    assert out["reason"] == "pass_ceiling"
    assert out["remaining"]["inbox"] == 4
    assert out["remaining"]["ready"] == 1
    assert out["remaining_source"] == "inflight_working"
    persisted = json.loads(receipt.read_text())
    assert persisted["reason"] == "pass_ceiling"
    assert persisted["remaining"]["inbox"] == 4
    assert persisted["remaining"] != stale


def test_remaining_from_inflight_working_counts_listed_rows_over_zero_counter(
    tmp_path,
):
    pass_dir = tmp_path / "factory-pass-9-abcd"
    pass_dir.mkdir()
    (pass_dir / "working.json").write_text(
        json.dumps(
            {
                "remaining_inbox": 0,
                "inbox_issues_by_repo": {
                    "mikolaj92/Temida": [
                        {"number": 4972, "labels": ["enhancement"]},
                        {"number": 4973, "labels": ["bug"]},
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    remaining = daemon_cycle.remaining_from_inflight_working(tmp_path)
    assert remaining["inbox"] == 2
    assert remaining["by_repo"][0]["repo"] == "mikolaj92/Temida"


def test_daemon_cycle_pass_ceiling_does_not_copy_stale_inbox_zero(
    monkeypatch, tmp_path
):
    cfg = _write_cfg(tmp_path)
    receipt = tmp_path / "lokay-state" / "last-pass.json"
    receipt.write_text(
        json.dumps({"remaining": {"inbox": 0, "ready": 0}}), encoding="utf-8"
    )

    def wait_forever(**_kwargs):
        import time

        time.sleep(1)
        return {"ok": True}

    monkeypatch.setattr(daemon_cycle, "run_path", wait_forever)
    out = daemon_cycle.compose_daemon_cycle(
        config_path=cfg,
        pass_ceiling_seconds=0.02,
    )

    assert out["reason"] == "pass_ceiling"
    assert "remaining" not in out
    persisted = json.loads(receipt.read_text())
    assert persisted["reason"] == "pass_ceiling"
    assert "remaining" not in persisted


def test_daemon_cycle_native_exception_after_ceiling_writes_receipt(
    monkeypatch, tmp_path
):
    cfg = _write_cfg(tmp_path)

    def native_like_failure(**_kwargs):
        import time

        try:
            time.sleep(1)
        except BaseException:
            raise Exception("") from None

    monkeypatch.setattr(daemon_cycle, "run_path", native_like_failure)
    out = daemon_cycle.compose_daemon_cycle(
        config_path=cfg,
        pass_ceiling_seconds=0.02,
    )

    assert out["reason"] == "pass_ceiling"
    receipt = tmp_path / "lokay-state" / "last-pass.json"
    assert json.loads(receipt.read_text())["reason"] == "pass_ceiling"


def test_daemon_cycle_native_exception_before_ceiling_propagates(monkeypatch, tmp_path):
    cfg = _write_cfg(tmp_path)
    monkeypatch.setattr(
        daemon_cycle,
        "run_path",
        lambda **_kwargs: (_ for _ in ()).throw(Exception("native failure")),
    )

    with pytest.raises(Exception, match="native failure"):
        daemon_cycle.compose_daemon_cycle(
            config_path=cfg,
            pass_ceiling_seconds=1,
        )


def test_daemon_cycle_short_pass_is_unchanged(monkeypatch, tmp_path):
    cfg = _write_cfg(tmp_path)
    expected = {"ok": True, "health": "idle"}
    monkeypatch.setattr(daemon_cycle, "run_path", lambda **_kwargs: expected)
    out = daemon_cycle.compose_daemon_cycle(
        config_path=cfg,
        pass_ceiling_seconds=1,
    )
    assert out["ok"] is True
    assert out["health"] == "idle"
    assert out.get("reason") != "pass_ceiling"


def test_daemon_progress_despite_fala_ok_false_exits_zero(
    monkeypatch, tmp_path, capsys
):
    cfg = _write_cfg(tmp_path)
    monkeypatch.setattr(daemon, "acquire_run_lock", lambda p: True)
    monkeypatch.setattr(daemon, "run_preflight", lambda *a, **k: {"ok": True})
    monkeypatch.setattr(
        "lokay.proc.daemon_entry_subflow.run",
        lambda **k: {"ok": False, "health": "progress", "progress": 1},
    )
    assert daemon.main(["--config", cfg, "--outbox", str(tmp_path / "out")]) == 0
    assert "progress" in capsys.readouterr().out


def test_os_pass_ceiling_kills_lock_owner_not_detached_worker(tmp_path):
    """Caretaker SIGTERM is the mill.lock release. Nested Fala SIGALRM is not."""
    import time

    extra = {
        "LOKAY_PASS_CEILING_SECONDS": "1",
        "LOKAY_UV_DAEMON_GATE": str(tmp_path / "never-finish"),
        "LOKAY_UV_DAEMON_MARKER": str(tmp_path / "daemon-started"),
    }
    started = time.monotonic()
    completed = _run_daemon(tmp_path, extra_env=extra)
    elapsed = time.monotonic() - started
    assert elapsed < 8, elapsed
    assert completed.returncode == 0, completed.stderr
    receipt = json.loads((tmp_path / ".lokay" / "last-pass.json").read_text(encoding="utf-8"))
    assert receipt["health"] == "pass_ceiling"
    assert receipt["reason"] == "pass_ceiling"
    latest = (tmp_path / ".lokay" / "logs" / "mill-latest.log").read_text(encoding="utf-8")
    assert "pass_ceiling" in latest
    assert (tmp_path / "daemon-started").exists()

