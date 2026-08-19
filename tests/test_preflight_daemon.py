import json
import os
import subprocess
from pathlib import Path

from lokay.compose import daemon_cycle
from lokay.compose.daemon_cycle import finalize_daemon_payload
from lokay.envelope import process_exit_code
from lokay.proc import daemon


def _script() -> Path:
    return Path(__file__).parents[1] / "scripts" / "lokay-mill-daemon.sh"


def test_daemon_bootstraps_before_uv_and_has_no_product_bypass():
    script = _script().read_text()
    assert script.index("command -v uv") < script.index("uv run lokay-host-ff")
    assert script.index("uv run lokay-host-ff") < script.index("uv run lokay-daemon")
    assert "uv run lokay-repos" not in script
    assert "uv run lokay-mill" not in script
    assert "preflight-bootstrap-incidents.log" in script
    assert "--reinstall-package lokay --reinstall-package fala" in script
    assert "uv-install.digest" in script
    assert 'export PYTHONPATH="${ROOT}/src' in script
    assert "package_matches()" in script
    assert '"health"[[:space:]]*:[[:space:]]*"overlap"' in script
    assert "host_updated" in script
    assert "emit_launchd_glance" in script
    assert "reopen_stdio_on_path" in script
    assert "loaded_plist_path" in script
    assert "os.ftruncate" in script
    assert "| tee " not in script
    assert 'lokay-host-ff --config "${CFG}" --live --checkout "${ROOT}" >>"${LOG}"' in script
    assert "lock_busy" in script
    assert "mill_lock_busy" in script


def test_daemon_handles_missing_home_and_bounds_bootstrap_outbox():
    script = _script().read_text()
    assert 'HOME="${HOME:-${TMPDIR:-/tmp}/lokay-${UID:-unknown}}"' in script
    assert 'wc -c < "${OUTBOX}"' in script
    assert "-ge 65536" in script
    assert ': > "${OUTBOX}"' in script
    assert "LOKAY_MILL_LOG_MAX" in script
    assert "LOKAY_LAUNCHD_STDOUT_MAX" in script


def _fake_uv(local_bin: Path) -> Path:
    uv = local_bin / "uv"
    uv.write_text(
        "#!/bin/sh\n"
        "log=${LOKAY_UV_ARGV_LOG:-}\n"
        'if [ -n "$log" ]; then printf \'%s\\n\' "$*" >> "$log"; fi\n'
        "if [ \"$1 $2\" = 'run lokay-host-ff' ]; then\n"
        "  printf '%s\\n' '{\"ok\":true,\"health\":\"current\"}'\n"
        "  exit 0\n"
        "fi\n"
        "if [ \"$LOKAY_UV_REINSTALL_FAIL\" = 1 ] && "
        "[ \"$1 $2 $3 $4 $5\" = 'run --reinstall-package lokay --reinstall-package fala' ]; then\n"
        "  echo 'error: failed to reinstall' >&2\n"
        "  exit 1\n"
        "fi\n"
        "if [ \"$1\" = run ] && [ \"$2\" = lokay-daemon ]; then\n"
        "  printf '%s\\n' \"$(command -v pi)\" \"$PATH\"\n"
        "  if [ -n \"$LOKAY_UV_ENVELOPE\" ]; then printf '%s\\n' \"$LOKAY_UV_ENVELOPE\"; else\n"
        "    printf '%s\\n' '{\"ok\":false,\"health\":\"progress\",\"progress\":1}'\n"
        "  fi\n"
        "  exit 0\n"
        "fi\n"
        "if [ \"$1 $2 $3 $4 $5\" = 'run --reinstall-package lokay --reinstall-package fala' ]; then\n"
        "  printf '%s\\n' \"$(command -v pi)\" \"$PATH\"\n"
        "  if [ -n \"$LOKAY_UV_ENVELOPE\" ]; then printf '%s\\n' \"$LOKAY_UV_ENVELOPE\"; else\n"
        "    printf '%s\\n' '{\"ok\":false,\"health\":\"progress\",\"progress\":1}'\n"
        "  fi\n"
        "  exit 0\n"
        "fi\n"
        "exit 64\n"
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
        "LOKAY_MILL_LOG_MAX": "4096",
        "LOKAY_LAUNCHD_STDOUT_MAX": "4096",
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


def test_daemon_exposes_local_pi_to_preflight(tmp_path):
    """Issue #15: exercise the shell boundary used by launchd, not only the
    Python PATH repair helper."""
    completed = _run_daemon(tmp_path)
    assert completed.returncode == 0, completed.stderr
    logs = list((tmp_path / ".lokay" / "logs").glob("mill-*.log"))
    assert logs
    transcript = next(path.read_text() for path in logs if path.name != "mill-latest.log")
    lines = [line for line in transcript.splitlines() if line]
    pi_line = next(i for i, line in enumerate(lines) if str(tmp_path / ".local" / "bin" / "pi") in line)
    assert lines[pi_line + 1].split(os.pathsep)[0] == str(tmp_path / ".local" / "bin")
    glance = json.loads(completed.stdout.strip().splitlines()[-1])
    assert glance["health"] == "progress"
    assert glance["progress"] == 1
    assert "engine" not in glance
    assert "fala" not in glance


def test_launchd_runs_host_ff_but_not_daemon_when_mill_lock_busy(tmp_path):
    import fcntl

    lock = tmp_path / ".lokay" / "mill.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    handle = lock.open("a+", encoding="utf-8")
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        completed = _run_daemon(tmp_path)
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()
    assert completed.returncode == 0, completed.stderr
    argv_log = tmp_path / "uv-argv.log"
    calls = argv_log.read_text(encoding="utf-8").splitlines()
    assert any("lokay-host-ff" in line for line in calls)
    assert all("lokay-daemon" not in line for line in calls)
    logs = list((tmp_path / ".lokay" / "logs").glob("mill-*.log"))
    body = "\n".join(path.read_text(encoding="utf-8") for path in logs)
    assert "lock_busy" in body


def test_second_tick_skips_uv_reinstall_when_digest_matches(tmp_path):
    first = _run_daemon(tmp_path)
    assert first.returncode == 0, first.stderr
    argv_log = tmp_path / "uv-argv.log"
    first_calls = argv_log.read_text(encoding="utf-8").splitlines()
    assert any("--reinstall-package lokay" in line for line in first_calls)
    argv_log.write_text("", encoding="utf-8")

    second = _run_daemon(tmp_path)
    assert second.returncode == 0, second.stderr
    second_calls = argv_log.read_text(encoding="utf-8").splitlines()
    assert second_calls
    assert all("--reinstall-package" not in line for line in second_calls)
    assert any(line.startswith("run lokay-daemon") for line in second_calls)


def test_mill_log_and_launchd_stdout_are_bounded(tmp_path):
    logs = tmp_path / ".lokay" / "logs"
    logs.mkdir(parents=True)
    fat = logs / "launchd-stdout.log"
    fat.write_bytes(b"x" * 8000)
    (tmp_path / ".lokay").mkdir(exist_ok=True)
    completed = _run_daemon(
        tmp_path,
        extra_env={"LOKAY_LAUNCHD_STDOUT_MAX": "2048"},
    )
    assert completed.returncode == 0, completed.stderr
    assert fat.stat().st_size < 4096
    assert b"truncated" in fat.read_bytes()
    mill_logs = [
        path
        for path in logs.glob("mill-*.log")
        if path.name != "mill-latest.log"
    ]
    assert mill_logs
    assert all(path.stat().st_size < 8192 for path in mill_logs)


def test_overlap_envelope_does_not_persist_digest(tmp_path):
    first = _run_daemon(
        tmp_path,
        extra_env={
            "LOKAY_UV_ENVELOPE": '{"ok":false,"health":"overlap","code":"overlap"}'
        },
    )
    # Fake uv exits 0; the envelope is overlap. Digest must stay open.
    assert first.returncode == 0, first.stderr
    digest = tmp_path / ".lokay" / "uv-install.digest"
    assert not digest.exists()
    argv_log = tmp_path / "uv-argv.log"
    argv_log.write_text("", encoding="utf-8")
    second = _run_daemon(tmp_path)
    assert second.returncode == 0, second.stderr
    second_calls = argv_log.read_text(encoding="utf-8").splitlines()
    assert any("--reinstall-package lokay" in line for line in second_calls)


def test_stale_site_packages_forces_reinstall_when_digest_matches(tmp_path):
    first = _run_daemon(tmp_path)
    assert first.returncode == 0, first.stderr
    digest = tmp_path / ".lokay" / "uv-install.digest"
    assert digest.is_file()
    argv_log = tmp_path / "uv-argv.log"
    argv_log.write_text("", encoding="utf-8")

    src = tmp_path / "repo" / "src" / "lokay"
    src.mkdir(parents=True)
    (src / "gh_rate.py").write_text("SURVEY_LIST_CAP = 1000\n", encoding="utf-8")
    stale = tmp_path / "repo" / ".venv" / "lib" / "python3.14" / "site-packages" / "lokay"
    stale.mkdir(parents=True)
    (stale / "gh_rate.py").write_text("old\n", encoding="utf-8")

    second = _run_daemon(tmp_path)
    assert second.returncode == 0, second.stderr
    second_calls = argv_log.read_text(encoding="utf-8").splitlines()
    assert any("--reinstall-package lokay" in line for line in second_calls)


def test_failed_uv_reinstall_does_not_persist_digest(tmp_path):
    first = _run_daemon(tmp_path, extra_env={"LOKAY_UV_REINSTALL_FAIL": "1"})
    assert first.returncode != 0
    digest = tmp_path / ".lokay" / "uv-install.digest"
    assert not digest.exists()
    argv_log = tmp_path / "uv-argv.log"
    argv_log.write_text("", encoding="utf-8")
    second = _run_daemon(tmp_path)
    assert second.returncode == 0, second.stderr
    second_calls = argv_log.read_text(encoding="utf-8").splitlines()
    assert any("--reinstall-package lokay" in line for line in second_calls)
    assert digest.is_file()


def test_open_launchd_stdout_stays_bounded_after_truncate(tmp_path):
    logs = tmp_path / ".lokay" / "logs"
    logs.mkdir(parents=True)
    fat = logs / "launchd-stdout.log"
    fat.write_bytes(b"x" * 8000)
    with fat.open("a", encoding="utf-8") as handle:
        completed = _run_daemon(
            tmp_path,
            extra_env={"LOKAY_LAUNCHD_STDOUT_MAX": "2048"},
            stdout=handle,
        )
        assert completed.returncode == 0, completed.stderr
        handle.flush()
        os.fsync(handle.fileno())
    assert fat.stat().st_size < 4096
    body = fat.read_text(encoding="utf-8", errors="replace")
    assert "truncated" in body
    glance = None
    for line in reversed(body.splitlines()):
        raw = line.strip()
        if raw.startswith("{") and raw.endswith("}"):
            glance = json.loads(raw)
            break
    assert glance is not None
    assert glance["health"] == "progress"


def test_glance_reads_nested_mill_health_from_truncated_envelope(tmp_path):
    fat = (
        '{"ok":false,"error":"soft recovery","fala":{"host":"'
        + ("x" * 4000)
        + '"},"mill":{"health":"progress","progress":3,"remaining":{"issue_to_pr_started":1}}}'
    )
    completed = _run_daemon(
        tmp_path,
        extra_env={
            "LOKAY_UV_ENVELOPE": fat,
            "LOKAY_MILL_LOG_MAX": "2048",
        },
    )
    assert completed.returncode == 0, completed.stderr
    glance = json.loads(completed.stdout.strip().splitlines()[-1])
    assert glance["health"] == "progress"
    assert glance["progress"] >= 1


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
    assert process_exit_code({"ok": False, "health": "host_updated", "reason": "host_updated"}) == 0
    assert process_exit_code({"ok": False, "health": "progress", "progress": 2}) == 0
    assert process_exit_code(
        {"ok": False, "remaining": {"issue_to_pr_started": 1}}
    ) == 0
    assert process_exit_code(
        {"ok": False, "mill": {"health": "progress", "progress": 1}}
    ) == 0
    assert process_exit_code({"ok": False, "health": "stall"}) == 1
    assert process_exit_code(
        {"ok": False},
        last_pass={"health": "progress", "progress": 4},
    ) == 0
    assert process_exit_code(
        {"ok": False, "health": "stall"},
        last_pass={"health": "progress", "progress": 4},
    ) == 1


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
    receipt = tmp_path / "lokay-state" / "last-pass.json"
    assert json.loads(receipt.read_text())["reason"] == "pass_ceiling"


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


def test_daemon_progress_despite_fala_ok_false_exits_zero(monkeypatch, tmp_path, capsys):
    cfg = _write_cfg(tmp_path)
    monkeypatch.setattr(daemon, "acquire_run_lock", lambda p: True)
    monkeypatch.setattr(daemon, "run_preflight", lambda *a, **k: {"ok": True})
    monkeypatch.setattr(
        daemon,
        "compose_daemon_cycle",
        lambda **k: {"ok": False, "health": "progress", "progress": 1},
    )
    assert daemon.main(["--config", cfg, "--outbox", str(tmp_path / "out")]) == 0
    assert '"health": "progress"' in capsys.readouterr().out
