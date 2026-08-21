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
    assert "idle_skip_daemon()" in script
    assert "host_ff_already_current()" in script
    assert "HOST_FF_MOVED" in script
    assert "Fresh idle skip with a persisted digest skips checkout_digest" in script
    assert '"already_current"[[:space:]]*:[[:space:]]*true' in script
    assert "already_current envelope already proved HEAD did not move" in script
    assert "Fresh idle skip already bounded launchd stdio" in script
    assert "Already under keep skips python" in script
    assert '"health":"idle","progress":0' in script
    assert "repos/mikolaj92/lokay/git/ref/heads/main" in script
    assert script.index("host_ff_already_current") < script.index("uv run lokay-host-ff")
    assert "recent_empty_survey" in script
    assert "recent_empty_survey_probe" in script
    assert "recent_empty_leftover_probe" in script
    assert "Mill-probe GitHub lists run together. Probe failure still hosts." in script
    assert "Leftover-probe GitHub lists run together. Probe failure still hosts." in script
    assert "Leftover-probe still hosts lokay-daemon so idle reap continues." in script
    assert "Leftover-probe still hosts lokay-daemon even when mill-probe would also run." in script
    assert "Leftover-probe skips GitHub SHA when survey stamp is still fresh." in script
    assert "Mill-probe skips GitHub SHA when leftover stamp is still fresh." in script
    assert "Combined leftover+survey expiry still probes SHA." in script
    assert "Trailing delayed --install checks keepalive stamp before mill_lock_busy." in script
    assert "ThreadPoolExecutor(max_workers=3)" in script
    assert "ThreadPoolExecutor(max_workers=2)" in script
    assert '"health"[[:space:]]*:[[:space:]]*"overlap"' in script
    assert "host_updated" in script
    assert "emit_launchd_glance" in script
    assert "reopen_stdio_on_path" in script
    assert "loaded_plist_path" in script
    assert "os.ftruncate" in script
    assert "wc -c <" in script
    assert 'size="${size// /}"' in script
    assert '[[ -n "${size}" && "${size}" -le "${LAUNCHD_STDOUT_MAX}" ]]' in script
    assert "skips python inode reopen" in script
    assert "Missing or XML plist skips python plistlib. Binary plist still python." in script
    assert '[[ "${magic}" == "bplist00" ]]' in script
    assert "Leave 1KiB glance headroom so later idle lines stay under the cap." in script
    assert "| tee " not in script
    assert 'lokay-host-ff --config "${CFG}" --live --checkout "${ROOT}" >>"${LOG}"' in script
    assert script.index('export LOKAY_HOST_FF_FETCHED="${LOKAY_HOST_FF_FETCHED:-}"') < script.index("uv run lokay-host-ff")
    assert script.index("uv run lokay-host-ff") < script.index("export LOKAY_HOST_FF_FETCHED=1")
    assert "lock_busy" in script
    assert "mill_lock_busy" in script
    assert "loaded_keepalive_crash_only" in script
    assert '{"SuccessfulExit": False}' in script
    assert "Already 60s crash KeepAlive skips python plistlib" in script
    assert "Cache python3 so later helpers skip command -v." in script
    assert "Fresh idle stamps skip python host_ff_already_current." in script
    assert "Fresh idle host proof uses two Git processes instead of four." in script
    assert "Fresh idle proof is cached within one tick; stamp expiry is cross-tick." in script
    assert "Fresh idle stamp age reuses one date +%s." in script
    assert "Fresh idle skip already bounded launchd stdio and defers mill-log pruning" in script
    assert "Fresh idle skip defers the first launchd stdio bound; hosted/probe ticks still bound." in script
    assert "Fresh idle stamps skip python idle_skip_daemon." in script
    assert "GNU epoch first. Linux stat -f is filesystem, not mtime." in script
    assert 'stat -c %Y' in script
    assert "plutil -extract StartInterval raw" in script
    assert '[[ "${HOME}" == /Users/* ]]' in script
    assert "os.setsid()" in script
    assert 'os.execv("/bin/bash", ["/bin/bash", script, "--install"])' in script
    assert "( sleep 2; exec /bin/bash" not in script


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
        "case \"$*\" in\n"
        "  *lokay-daemon*)\n"
        "    if [ -n \"$LOKAY_UV_DAEMON_MARKER\" ]; then : > \"$LOKAY_UV_DAEMON_MARKER\"; fi\n"
        "    while [ -n \"$LOKAY_UV_DAEMON_GATE\" ] && [ ! -e \"$LOKAY_UV_DAEMON_GATE\" ]; do sleep 0.01; done\n"
        "    ;;\n"
        "esac\n"
        "if [ \"$1 $2\" = 'run lokay-host-ff' ]; then\n"
        "  if [ -n \"$LOKAY_UV_HOST_FF_ENVELOPE\" ]; then\n"
        "    printf '%s\\n' \"$LOKAY_UV_HOST_FF_ENVELOPE\"\n"
        "  else\n"
        "    printf '%s\\n' '{\"ok\":true,\"health\":\"current\",\"updated\":false,\"already_current\":true}'\n"
        "  fi\n"
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


def test_host_ff_updated_starts_daemon_same_tick(tmp_path):
    completed = _run_daemon(
        tmp_path,
        extra_env={
            "LOKAY_UV_HOST_FF_ENVELOPE": (
                '{"ok":true,"health":"current","updated":true,'
                '"already_current":false,"head":"abc"}'
            )
        },
    )
    assert completed.returncode == 0, completed.stderr
    argv_log = tmp_path / "uv-argv.log"
    calls = argv_log.read_text(encoding="utf-8").splitlines()
    assert any("lokay-host-ff" in line for line in calls)
    assert any("lokay-daemon" in line for line in calls)
    logs = list((tmp_path / ".lokay" / "logs").glob("mill-*.log"))
    body = "\n".join(path.read_text(encoding="utf-8") for path in logs)
    assert '"updated": true' in body or '"updated":true' in body
    glance = json.loads(completed.stdout.strip().splitlines()[-1])
    assert glance["health"] == "progress"
    assert any("--reinstall-package" in line and "lokay-daemon" in line for line in calls)


def test_host_ff_already_current_still_starts_daemon(tmp_path):
    completed = _run_daemon(tmp_path)
    assert completed.returncode == 0, completed.stderr
    argv_log = tmp_path / "uv-argv.log"
    calls = argv_log.read_text(encoding="utf-8").splitlines()
    assert any("lokay-host-ff" in line for line in calls)
    assert any("lokay-daemon" in line for line in calls)


def _github_checkout(root: Path) -> str:
    subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True, capture_output=True)
    (root / "README").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "add", "README"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "i"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "git@github.com:mikolaj92/lokay.git"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "update-ref", "refs/remotes/origin/main", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _write_gh_sha(tmp_path: Path, sha: str, *, empty_lists: bool = False) -> None:
    gh = tmp_path / ".local" / "bin" / "gh"
    gh.parent.mkdir(parents=True, exist_ok=True)
    if empty_lists:
        body = (
            "#!/bin/sh\n"
            'case " $* " in\n'
            f"  *git/ref/heads/main*) printf '%s\\n' '{sha}' ;;\n"
            "  *) printf '%s\\n' '[]' ;;\n"
            "esac\n"
            "exit 0\n"
        )
    else:
        body = "#!/bin/sh\nprintf '%s\\n' '" + sha + "'\nexit 0\n"
    gh.write_text(body, encoding="utf-8")
    gh.chmod(0o755)


def test_github_sha_match_skips_lokay_host_ff(tmp_path):
    first = _run_daemon(tmp_path)
    assert first.returncode == 0, first.stderr
    root = tmp_path / "repo"
    head = _github_checkout(root)
    _write_gh_sha(tmp_path, head)
    argv_log = tmp_path / "uv-argv.log"
    argv_log.write_text("", encoding="utf-8")
    second = _run_daemon(tmp_path)
    assert second.returncode == 0, second.stderr
    calls = argv_log.read_text(encoding="utf-8").splitlines()
    assert all("lokay-host-ff" not in line for line in calls)
    assert any("lokay-daemon" in line for line in calls)
    logs = list((tmp_path / ".lokay" / "logs").glob("mill-*.log"))
    body = chr(10).join(path.read_text(encoding="utf-8") for path in logs)
    assert "already_current" in body


def test_github_sha_probe_failure_still_runs_host_ff(tmp_path):
    first = _run_daemon(tmp_path)
    assert first.returncode == 0, first.stderr
    _github_checkout(tmp_path / "repo")
    gh = tmp_path / ".local" / "bin" / "gh"
    gh.parent.mkdir(parents=True, exist_ok=True)
    gh.write_text("#!/bin/sh\necho fail >&2\nexit 1\n", encoding="utf-8")
    gh.chmod(0o755)
    argv_log = tmp_path / "uv-argv.log"
    argv_log.write_text("", encoding="utf-8")
    second = _run_daemon(tmp_path)
    assert second.returncode == 0, second.stderr
    calls = argv_log.read_text(encoding="utf-8").splitlines()
    assert any("lokay-host-ff" in line for line in calls)


def test_github_sha_mismatch_still_runs_host_ff(tmp_path):
    first = _run_daemon(tmp_path)
    assert first.returncode == 0, first.stderr
    _github_checkout(tmp_path / "repo")
    _write_gh_sha(tmp_path, "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef")
    argv_log = tmp_path / "uv-argv.log"
    argv_log.write_text("", encoding="utf-8")
    second = _run_daemon(tmp_path)
    assert second.returncode == 0, second.stderr
    calls = argv_log.read_text(encoding="utf-8").splitlines()
    assert any("lokay-host-ff" in line for line in calls)


def test_idle_github_sha_match_skips_host_ff_and_daemon(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "config.yaml").touch()
    head = _github_checkout(root)
    _write_gh_sha(tmp_path, head, empty_lists=True)
    first = _run_daemon(tmp_path)
    assert first.returncode == 0, first.stderr
    lokay = tmp_path / ".lokay"
    (lokay / "last-pass.json").write_text(_idle_receipt(), encoding="utf-8")
    (lokay / "factory-survey.stamp").write_text("1", encoding="utf-8")
    (lokay / "leftover-closeout.stamp").write_text("1", encoding="utf-8")
    argv_log = tmp_path / "uv-argv.log"
    argv_log.write_text("", encoding="utf-8")
    second = _run_daemon(tmp_path)
    assert second.returncode == 0, second.stderr
    calls = argv_log.read_text(encoding="utf-8").splitlines()
    assert all("lokay-host-ff" not in line for line in calls)
    assert all("lokay-daemon" not in line for line in calls)
    logs = list((lokay / "logs").glob("mill-*.log"))
    body = chr(10).join(path.read_text(encoding="utf-8") for path in logs)
    assert "recent_empty_survey" in body
    assert "already_current" in body


def _idle_receipt() -> str:
    return json.dumps(
        {
            "health": "idle",
            "idle": True,
            "remaining": {
                "inbox": 0,
                "ready": 0,
                "open_ai_prs": 0,
                "issue_to_pr_started": 0,
                "survey_errors": 0,
                "by_repo": [{"repo": "mikolaj92/lokay", "occupied": False}],
            },
        }
    )


def test_idle_stamps_skip_lokay_daemon_after_digest(tmp_path):
    first = _run_daemon(tmp_path)
    assert first.returncode == 0, first.stderr
    lokay = tmp_path / ".lokay"
    (lokay / "last-pass.json").write_text(_idle_receipt(), encoding="utf-8")
    (lokay / "factory-survey.stamp").write_text("1", encoding="utf-8")
    (lokay / "leftover-closeout.stamp").write_text("1", encoding="utf-8")
    argv_log = tmp_path / "uv-argv.log"
    argv_log.write_text("", encoding="utf-8")
    second = _run_daemon(tmp_path)
    assert second.returncode == 0, second.stderr
    calls = argv_log.read_text(encoding="utf-8").splitlines()
    assert any("lokay-host-ff" in line for line in calls)
    assert all("lokay-daemon" not in line for line in calls)
    logs = list((lokay / "logs").glob("mill-*.log"))
    body = "\n".join(path.read_text(encoding="utf-8") for path in logs)
    assert "recent_empty_survey" in body
    glance = json.loads(second.stdout.strip().splitlines()[-1])
    assert glance["health"] == "idle"
    assert glance["progress"] == 0


def test_idle_stamps_skip_python_idle_skip_daemon(tmp_path):
    """Fresh idle stamps skip python idle_skip_daemon. Occupied still hosts."""
    first = _run_daemon(tmp_path)
    assert first.returncode == 0, first.stderr
    lokay = tmp_path / ".lokay"
    receipt = lokay / "last-pass.json"
    receipt.write_text(_idle_receipt(), encoding="utf-8")
    (lokay / "factory-survey.stamp").write_text("1", encoding="utf-8")
    (lokay / "leftover-closeout.stamp").write_text("1", encoding="utf-8")
    argv_log = tmp_path / "uv-argv.log"
    argv_log.write_text("", encoding="utf-8")
    wrapper = tmp_path / "pywrap"
    log = tmp_path / "pywrap.log"
    wrapper.write_text(
        chr(10).join(
            [
                "#!/bin/sh",
                "printf '%s\\n' \"$*\" >> '" + str(log) + "'",
                'exec /usr/bin/python3 "$@"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    second = _run_daemon(tmp_path, extra_env={"LOKAY_PYTHON3": str(wrapper)})
    assert second.returncode == 0, second.stderr
    calls = argv_log.read_text(encoding="utf-8").splitlines()
    assert all("lokay-daemon" not in line for line in calls)
    logs = list((lokay / "logs").glob("mill-*.log"))
    body = chr(10).join(path.read_text(encoding="utf-8") for path in logs)
    assert "recent_empty_survey" in body
    assert log.is_file()
    # idle_skip_daemon python argv starts with last-pass.json.
    # host_ff python still runs on local clones and also sees that path.
    assert not any(
        line.split()[:2] == ["-", str(receipt)]
        for line in log.read_text(encoding="utf-8").splitlines()
    )


def test_idle_stamps_skip_github_sha_probe(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "config.yaml").touch()
    _github_checkout(root)
    gh = tmp_path / ".local" / "bin" / "gh"
    gh.parent.mkdir(parents=True, exist_ok=True)
    gh.write_text("#!/bin/sh\necho fail >&2\nexit 1\n", encoding="utf-8")
    gh.chmod(0o755)
    first = _run_daemon(tmp_path)
    assert first.returncode == 0, first.stderr
    lokay = tmp_path / ".lokay"
    (lokay / "last-pass.json").write_text(_idle_receipt(), encoding="utf-8")
    (lokay / "factory-survey.stamp").write_text("1", encoding="utf-8")
    (lokay / "leftover-closeout.stamp").write_text("1", encoding="utf-8")
    argv_log = tmp_path / "uv-argv.log"
    argv_log.write_text("", encoding="utf-8")
    second = _run_daemon(tmp_path)
    assert second.returncode == 0, second.stderr
    calls = argv_log.read_text(encoding="utf-8").splitlines()
    assert all("lokay-host-ff" not in line for line in calls)
    assert all("lokay-daemon" not in line for line in calls)
    logs = list((lokay / "logs").glob("mill-*.log"))
    body = chr(10).join(path.read_text(encoding="utf-8") for path in logs)
    assert "recent_empty_survey" in body
    assert "already_current" in body


def test_idle_stamps_skip_python_host_ff_already_current(tmp_path):
    """Fresh idle stamps skip python host_ff_already_current. Busy lock still probes."""
    root = tmp_path / "repo"
    root.mkdir()
    (root / "config.yaml").touch()
    _github_checkout(root)
    gh = tmp_path / ".local" / "bin" / "gh"
    gh.parent.mkdir(parents=True, exist_ok=True)
    gh.write_text("#!/bin/sh" + chr(10) + "echo fail >&2" + chr(10) + "exit 1" + chr(10), encoding="utf-8")
    gh.chmod(0o755)
    first = _run_daemon(tmp_path)
    assert first.returncode == 0, first.stderr
    lokay = tmp_path / ".lokay"
    (lokay / "last-pass.json").write_text(_idle_receipt(), encoding="utf-8")
    (lokay / "factory-survey.stamp").write_text("1", encoding="utf-8")
    (lokay / "leftover-closeout.stamp").write_text("1", encoding="utf-8")
    argv_log = tmp_path / "uv-argv.log"
    argv_log.write_text("", encoding="utf-8")
    wrapper = tmp_path / "pywrap"
    log = tmp_path / "pywrap.log"
    wrapper.write_text(
        chr(10).join(
            [
                "#!/bin/sh",
                "printf '%s\\n' \"$*\" >> '" + str(log) + "'",
                'exec /usr/bin/python3 "$@"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    second = _run_daemon(tmp_path, extra_env={"LOKAY_PYTHON3": str(wrapper)})
    assert second.returncode == 0, second.stderr
    calls = argv_log.read_text(encoding="utf-8").splitlines()
    assert all("lokay-host-ff" not in line for line in calls)
    assert all("lokay-daemon" not in line for line in calls)
    logs = list((lokay / "logs").glob("mill-*.log"))
    body = chr(10).join(path.read_text(encoding="utf-8") for path in logs)
    assert "already_current" in body
    # Missing or XML plist skips python launchd_stdout_paths. GitHub CLEAN
    # skip may pay no python at all.
    if log.is_file():
        assert str(root) not in log.read_text(encoding="utf-8")
    assert "rev-parse HEAD origin/main --abbrev-ref HEAD" in _script().read_text()
    assert _script().read_text().count('git -C "${checkout}"') == 2
    assert 'LOKAY_IDLE_STAMPS_FRESH=1' in _script().read_text()
    assert _script().read_text().count('_stamp_age_seconds "${LOKAY_HOME}/') == 4
    assert 'now="$(date +%s)" || return 1' in _script().read_text()
    assert '_stamp_age_seconds "${LOKAY_HOME}/leftover-closeout.stamp" "${now}"' in _script().read_text()
    assert '_stamp_age_seconds "${LOKAY_HOME}/factory-survey.stamp" "${now}"' in _script().read_text()


def test_idle_skip_does_not_reinstall_stale_wheel_until_stamps_expire(tmp_path):
    first = _run_daemon(tmp_path)
    assert first.returncode == 0, first.stderr
    digest = tmp_path / ".lokay" / "uv-install.digest"
    assert digest.is_file()
    src = tmp_path / "repo" / "src" / "lokay"
    src.mkdir(parents=True)
    (src / "gh_rate.py").write_text("SURVEY_LIST_CAP = 1000\n", encoding="utf-8")
    stale = tmp_path / "repo" / ".venv" / "lib" / "python3.14" / "site-packages" / "lokay"
    stale.mkdir(parents=True)
    (stale / "gh_rate.py").write_text("old\n", encoding="utf-8")
    lokay = tmp_path / ".lokay"
    (lokay / "last-pass.json").write_text(_idle_receipt(), encoding="utf-8")
    (lokay / "factory-survey.stamp").write_text("1", encoding="utf-8")
    (lokay / "leftover-closeout.stamp").write_text("1", encoding="utf-8")
    argv_log = tmp_path / "uv-argv.log"
    argv_log.write_text("", encoding="utf-8")
    second = _run_daemon(tmp_path)
    assert second.returncode == 0, second.stderr
    second_calls = argv_log.read_text(encoding="utf-8").splitlines()
    assert all("lokay-daemon" not in line for line in second_calls)
    assert all("--reinstall-package" not in line for line in second_calls)
    argv_log.write_text("", encoding="utf-8")
    _expire(lokay / "factory-survey.stamp", 200)
    _write_empty_gh(tmp_path)
    third = _run_daemon(tmp_path)
    assert third.returncode == 0, third.stderr
    third_calls = argv_log.read_text(encoding="utf-8").splitlines()
    assert any("--reinstall-package lokay" in line for line in third_calls)


def test_busy_lock_still_probes_github_sha(tmp_path):
    import fcntl

    root = tmp_path / "repo"
    root.mkdir()
    (root / "config.yaml").touch()
    _github_checkout(root)
    gh = tmp_path / ".local" / "bin" / "gh"
    gh.parent.mkdir(parents=True, exist_ok=True)
    gh.write_text("#!/bin/sh\necho fail >&2\nexit 1\n", encoding="utf-8")
    gh.chmod(0o755)
    first = _run_daemon(tmp_path)
    assert first.returncode == 0, first.stderr
    lokay = tmp_path / ".lokay"
    (lokay / "last-pass.json").write_text(_idle_receipt(), encoding="utf-8")
    (lokay / "factory-survey.stamp").write_text("1", encoding="utf-8")
    (lokay / "leftover-closeout.stamp").write_text("1", encoding="utf-8")
    argv_log = tmp_path / "uv-argv.log"
    argv_log.write_text("", encoding="utf-8")
    lock = lokay / "mill.lock"
    handle = lock.open("a+", encoding="utf-8")
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        second = _run_daemon(tmp_path)
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()
    assert second.returncode == 0, second.stderr
    calls = argv_log.read_text(encoding="utf-8").splitlines()
    assert any("lokay-host-ff" in line for line in calls)
    assert all("lokay-daemon" not in line for line in calls)


def test_idle_skip_hosts_when_survey_stamp_missing(tmp_path):
    first = _run_daemon(tmp_path)
    assert first.returncode == 0, first.stderr
    lokay = tmp_path / ".lokay"
    (lokay / "last-pass.json").write_text(_idle_receipt(), encoding="utf-8")
    (lokay / "leftover-closeout.stamp").write_text("1", encoding="utf-8")
    argv_log = tmp_path / "uv-argv.log"
    argv_log.write_text("", encoding="utf-8")
    second = _run_daemon(tmp_path)
    assert second.returncode == 0, second.stderr
    calls = argv_log.read_text(encoding="utf-8").splitlines()
    assert any("lokay-daemon" in line for line in calls)


def test_idle_skip_hosts_when_occupied(tmp_path):
    first = _run_daemon(tmp_path)
    assert first.returncode == 0, first.stderr
    lokay = tmp_path / ".lokay"
    receipt = json.loads(_idle_receipt())
    receipt["remaining"]["by_repo"] = [{"repo": "mikolaj92/lokay", "occupied": True}]
    (lokay / "last-pass.json").write_text(json.dumps(receipt), encoding="utf-8")
    (lokay / "factory-survey.stamp").write_text("1", encoding="utf-8")
    (lokay / "leftover-closeout.stamp").write_text("1", encoding="utf-8")
    argv_log = tmp_path / "uv-argv.log"
    argv_log.write_text("", encoding="utf-8")
    second = _run_daemon(tmp_path)
    assert second.returncode == 0, second.stderr
    calls = argv_log.read_text(encoding="utf-8").splitlines()
    assert any("lokay-daemon" in line for line in calls)


def _write_empty_gh(tmp_path: Path) -> None:
    gh = tmp_path / ".local" / "bin" / "gh"
    gh.parent.mkdir(parents=True, exist_ok=True)
    gh.write_text("#!/bin/sh\nprintf '%s\\n' '[]'\nexit 0\n", encoding="utf-8")
    gh.chmod(0o755)


def _expire(path: Path, age: int) -> None:
    import time

    path.write_text("1", encoding="utf-8")
    stamp = time.time() - age
    os.utime(path, (stamp, stamp))


def test_idle_expired_survey_empty_probe_skips_lokay_daemon(tmp_path):
    """Mill-probe skips GitHub SHA when leftover stamp is still fresh."""
    root = tmp_path / "repo"
    root.mkdir()
    (root / "config.yaml").touch()
    _github_checkout(root)
    first = _run_daemon(tmp_path)
    assert first.returncode == 0, first.stderr
    lokay = tmp_path / ".lokay"
    (lokay / "last-pass.json").write_text(_idle_receipt(), encoding="utf-8")
    survey = lokay / "factory-survey.stamp"
    leftover = lokay / "leftover-closeout.stamp"
    leftover.write_text("1", encoding="utf-8")
    _expire(survey, 200)
    before = survey.stat().st_mtime
    gh = tmp_path / ".local" / "bin" / "gh"
    gh.parent.mkdir(parents=True, exist_ok=True)
    gh.write_text(
        chr(10).join(
            [
                "#!/bin/sh",
                'case " $* " in',
                "  *git/ref/heads/main*) echo fail >&2; exit 1 ;;",
                "  *) printf '%s\n' '[]' ;;",
                "esac",
                "exit 0",
                "",
            ]
        ),
        encoding="utf-8",
    )
    gh.chmod(0o755)
    argv_log = tmp_path / "uv-argv.log"
    argv_log.write_text("", encoding="utf-8")
    second = _run_daemon(tmp_path)
    assert second.returncode == 0, second.stderr
    calls = argv_log.read_text(encoding="utf-8").splitlines()
    assert all("lokay-host-ff" not in line for line in calls)
    assert all("lokay-daemon" not in line for line in calls)
    logs = list((lokay / "logs").glob("mill-*.log"))
    body = chr(10).join(path.read_text(encoding="utf-8") for path in logs)
    assert "recent_empty_survey_probe" in body
    assert "already_current" in body
    assert survey.stat().st_mtime > before


def test_idle_expired_survey_probe_lists_run_together(tmp_path):
    first = _run_daemon(tmp_path)
    assert first.returncode == 0, first.stderr
    lokay = tmp_path / ".lokay"
    (lokay / "last-pass.json").write_text(_idle_receipt(), encoding="utf-8")
    survey = lokay / "factory-survey.stamp"
    leftover = lokay / "leftover-closeout.stamp"
    leftover.write_text("1", encoding="utf-8")
    _expire(survey, 200)
    starts = tmp_path / "gh-starts"
    gh = tmp_path / ".local" / "bin" / "gh"
    gh.parent.mkdir(parents=True, exist_ok=True)
    gh.write_text(
        "#!/bin/sh\n"
        f"starts='{starts}'\n"
        'case " $* " in\n'
        '  *" pr list "*|*" issue list "*)\n'
        "    python3 -c \"import time; print(time.time())\" >> \"$starts\"\n"
        "    sleep 0.2\n"
        "    printf '%s\\n' '[]'\n"
        "    ;;\n"
        "  *) printf '%s\\n' '[]' ;;\n"
        "esac\n"
        "exit 0\n",
        encoding="utf-8",
    )
    gh.chmod(0o755)
    argv_log = tmp_path / "uv-argv.log"
    argv_log.write_text("", encoding="utf-8")
    second = _run_daemon(tmp_path)
    assert second.returncode == 0, second.stderr
    calls = argv_log.read_text(encoding="utf-8").splitlines()
    assert all("lokay-daemon" not in line for line in calls)
    logs = list((lokay / "logs").glob("mill-*.log"))
    body = chr(10).join(path.read_text(encoding="utf-8") for path in logs)
    assert "recent_empty_survey_probe" in body
    stamps = [float(line) for line in starts.read_text(encoding="utf-8").split() if line.strip()]
    assert len(stamps) == 3
    assert max(stamps) - min(stamps) < 0.15


def test_idle_expired_survey_probe_failure_hosts(tmp_path):
    first = _run_daemon(tmp_path)
    assert first.returncode == 0, first.stderr
    lokay = tmp_path / ".lokay"
    (lokay / "last-pass.json").write_text(_idle_receipt(), encoding="utf-8")
    survey = lokay / "factory-survey.stamp"
    leftover = lokay / "leftover-closeout.stamp"
    leftover.write_text("1", encoding="utf-8")
    _expire(survey, 200)
    before = survey.stat().st_mtime
    gh = tmp_path / ".local" / "bin" / "gh"
    gh.parent.mkdir(parents=True, exist_ok=True)
    gh.write_text("#!/bin/sh\necho fail >&2\nexit 1\n", encoding="utf-8")
    gh.chmod(0o755)
    argv_log = tmp_path / "uv-argv.log"
    argv_log.write_text("", encoding="utf-8")
    second = _run_daemon(tmp_path)
    assert second.returncode == 0, second.stderr
    calls = argv_log.read_text(encoding="utf-8").splitlines()
    assert any("lokay-daemon" in line for line in calls)
    assert abs(survey.stat().st_mtime - before) < 1


def test_idle_expired_leftover_empty_probe_still_hosts_lokay_daemon(tmp_path):
    """Leftover-probe still hosts lokay-daemon so idle reap continues."""
    root = tmp_path / "repo"
    root.mkdir()
    (root / "config.yaml").touch()
    _github_checkout(root)
    first = _run_daemon(tmp_path)
    assert first.returncode == 0, first.stderr
    lokay = tmp_path / ".lokay"
    (lokay / "last-pass.json").write_text(_idle_receipt(), encoding="utf-8")
    survey = lokay / "factory-survey.stamp"
    leftover = lokay / "leftover-closeout.stamp"
    survey.write_text("1", encoding="utf-8")
    _expire(leftover, 400)
    before = leftover.stat().st_mtime
    gh = tmp_path / ".local" / "bin" / "gh"
    gh.parent.mkdir(parents=True, exist_ok=True)
    gh.write_text(
        chr(10).join(
            [
                "#!/bin/sh",
                'case " $* " in',
                "  *git/ref/heads/main*) echo fail >&2; exit 1 ;;",
                "  *) printf '%s\n' '[]' ;;",
                "esac",
                "exit 0",
                "",
            ]
        ),
        encoding="utf-8",
    )
    gh.chmod(0o755)
    argv_log = tmp_path / "uv-argv.log"
    argv_log.write_text("", encoding="utf-8")
    second = _run_daemon(tmp_path)
    assert second.returncode == 0, second.stderr
    calls = argv_log.read_text(encoding="utf-8").splitlines()
    assert all("lokay-host-ff" not in line for line in calls)
    assert any("lokay-daemon" in line for line in calls)
    logs = list((lokay / "logs").glob("mill-*.log"))
    body = chr(10).join(path.read_text(encoding="utf-8") for path in logs)
    assert "recent_empty_leftover_probe" in body
    assert "already_current" in body
    assert leftover.stat().st_mtime > before


def test_idle_expired_leftover_and_survey_probe_still_hosts_lokay_daemon(tmp_path):
    """Leftover-probe still hosts lokay-daemon even when mill-probe would also run."""
    first = _run_daemon(tmp_path)
    assert first.returncode == 0, first.stderr
    lokay = tmp_path / ".lokay"
    (lokay / "last-pass.json").write_text(_idle_receipt(), encoding="utf-8")
    survey = lokay / "factory-survey.stamp"
    leftover = lokay / "leftover-closeout.stamp"
    _expire(survey, 200)
    _expire(leftover, 400)
    leftover_before = leftover.stat().st_mtime
    survey_before = survey.stat().st_mtime
    _write_empty_gh(tmp_path)
    argv_log = tmp_path / "uv-argv.log"
    argv_log.write_text("", encoding="utf-8")
    second = _run_daemon(tmp_path)
    assert second.returncode == 0, second.stderr
    calls = argv_log.read_text(encoding="utf-8").splitlines()
    assert any("lokay-host-ff" in line for line in calls)
    assert any("lokay-daemon" in line for line in calls)
    logs = list((lokay / "logs").glob("mill-*.log"))
    body = chr(10).join(path.read_text(encoding="utf-8") for path in logs)
    assert "recent_empty_leftover_probe" in body
    assert leftover.stat().st_mtime > leftover_before
    assert survey.stat().st_mtime > survey_before


def test_idle_expired_leftover_probe_lists_run_together(tmp_path):
    first = _run_daemon(tmp_path)
    assert first.returncode == 0, first.stderr
    lokay = tmp_path / ".lokay"
    (lokay / "last-pass.json").write_text(_idle_receipt(), encoding="utf-8")
    survey = lokay / "factory-survey.stamp"
    leftover = lokay / "leftover-closeout.stamp"
    survey.write_text("1", encoding="utf-8")
    _expire(leftover, 400)
    starts = tmp_path / "gh-starts"
    gh = tmp_path / ".local" / "bin" / "gh"
    gh.parent.mkdir(parents=True, exist_ok=True)
    gh.write_text(
        "#!/bin/sh\n"
        f"starts='{starts}'\n"
        'case " $* " in\n'
        '  *" issue list "*)\n'
        "    python3 -c \"import time; print(time.time())\" >> \"$starts\"\n"
        "    sleep 0.2\n"
        "    printf '%s\\n' '[]'\n"
        "    ;;\n"
        "  *) printf '%s\\n' '[]' ;;\n"
        "esac\n"
        "exit 0\n",
        encoding="utf-8",
    )
    gh.chmod(0o755)
    argv_log = tmp_path / "uv-argv.log"
    argv_log.write_text("", encoding="utf-8")
    second = _run_daemon(tmp_path)
    assert second.returncode == 0, second.stderr
    calls = argv_log.read_text(encoding="utf-8").splitlines()
    assert any("lokay-daemon" in line for line in calls)
    logs = list((lokay / "logs").glob("mill-*.log"))
    body = chr(10).join(path.read_text(encoding="utf-8") for path in logs)
    assert "recent_empty_leftover_probe" in body
    stamps = [float(line) for line in starts.read_text(encoding="utf-8").split() if line.strip()]
    assert len(stamps) == 2
    assert max(stamps) - min(stamps) < 0.15


def test_idle_expired_leftover_remaining_hosts(tmp_path):
    first = _run_daemon(tmp_path)
    assert first.returncode == 0, first.stderr
    lokay = tmp_path / ".lokay"
    (lokay / "last-pass.json").write_text(_idle_receipt(), encoding="utf-8")
    survey = lokay / "factory-survey.stamp"
    leftover = lokay / "leftover-closeout.stamp"
    survey.write_text("1", encoding="utf-8")
    _expire(leftover, 400)
    before = leftover.stat().st_mtime
    gh = tmp_path / ".local" / "bin" / "gh"
    gh.parent.mkdir(parents=True, exist_ok=True)
    gh.write_text(
        "#!/bin/sh\nprintf '%s\\n' '[{\"number\":1,\"state\":\"CLOSED\"}]'\nexit 0\n",
        encoding="utf-8",
    )
    gh.chmod(0o755)
    argv_log = tmp_path / "uv-argv.log"
    argv_log.write_text("", encoding="utf-8")
    second = _run_daemon(tmp_path)
    assert second.returncode == 0, second.stderr
    calls = argv_log.read_text(encoding="utf-8").splitlines()
    assert any("lokay-daemon" in line for line in calls)
    assert abs(leftover.stat().st_mtime - before) < 1


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


def test_install_writes_crash_keepalive_on_existing_plist(tmp_path):
    import plistlib

    plist = tmp_path / "probe.plist"
    plistlib.dump(
        {"Label": "ai.mikolaj.lokay-mill-test-keepalive", "StartInterval": 600},
        plist.open("wb"),
    )
    env = {
        "HOME": str(tmp_path),
        "PATH": "/usr/bin:/bin",
        "LOKAY_LAUNCHD_PLIST": str(plist),
        "LOKAY_LAUNCHD_LABEL": "ai.mikolaj.lokay-mill-test-keepalive",
    }
    completed = subprocess.run(
        ["/bin/bash", str(_script()), "--install"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    data = plistlib.load(plist.open("rb"))
    assert data["StartInterval"] == 60
    assert data["KeepAlive"] == {"SuccessfulExit": False}
    stamp = tmp_path / ".lokay" / "launchd-keepalive.stamp"
    assert stamp.exists()


def test_lokay_python3_env_is_cached_for_helpers(tmp_path):
    wrapper = tmp_path / "pywrap"
    log = tmp_path / "pywrap.log"
    wrapper.write_text(
        "#!/bin/sh\n"
        f"printf called\\n >> '{log}'\n"
        'exec /usr/bin/python3 "$@"\n',
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    completed = _run_daemon(tmp_path, extra_env={"LOKAY_PYTHON3": str(wrapper)})
    assert completed.returncode == 0, completed.stderr
    assert log.is_file()
    assert log.read_text(encoding="utf-8").count("called") >= 1


def test_already_crash_keepalive_skips_python_plistlib(tmp_path):
    import plistlib

    plist = tmp_path / "probe.plist"
    plistlib.dump(
        {
            "Label": "ai.mikolaj.lokay-mill-test-keepalive-already",
            "StartInterval": 60,
            "KeepAlive": {"SuccessfulExit": False},
        },
        plist.open("wb"),
    )
    before = plist.read_bytes()
    env = {
        "HOME": str(tmp_path),
        "PATH": "/usr/bin:/bin",
        "LOKAY_LAUNCHD_PLIST": str(plist),
        "LOKAY_LAUNCHD_LABEL": "ai.mikolaj.lokay-mill-test-keepalive-already",
    }
    completed = subprocess.run(
        ["/bin/bash", str(_script()), "--install"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert plist.read_bytes() == before


def test_install_does_not_invent_a_missing_plist(tmp_path):
    plist = tmp_path / "missing.plist"
    env = {
        "HOME": str(tmp_path),
        "PATH": "/usr/bin:/bin",
        "LOKAY_LAUNCHD_PLIST": str(plist),
        "LOKAY_LAUNCHD_LABEL": "ai.mikolaj.lokay-mill-test-keepalive-missing",
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


def test_pytest_home_does_not_spawn_delayed_install(tmp_path):
    completed = _run_daemon(tmp_path)
    assert completed.returncode == 0, completed.stderr
    stamp = tmp_path / ".lokay" / "launchd-keepalive.stamp"
    assert not stamp.exists()


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


def test_pass_ceiling_persists_digest_and_next_tick_skips_reinstall(tmp_path):
    first = _run_daemon(
        tmp_path,
        extra_env={"LOKAY_UV_ENVELOPE": '{"ok":false,"health":"pass_ceiling"}'},
    )
    assert first.returncode == 0, first.stderr
    digest = tmp_path / ".lokay" / "uv-install.digest"
    assert digest.is_file()

    argv_log = tmp_path / "uv-argv.log"
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


def test_small_launchd_stdout_skips_python_reopen(tmp_path):
    logs = tmp_path / ".lokay" / "logs"
    logs.mkdir(parents=True)
    small = logs / "launchd-stdout.log"
    body = b"idle glance\n"
    small.write_bytes(body)
    completed = _run_daemon(
        tmp_path,
        extra_env={"LOKAY_LAUNCHD_STDOUT_MAX": "2048"},
    )
    assert completed.returncode == 0, completed.stderr
    assert small.read_bytes() == body
    assert b"truncated" not in small.read_bytes()


def test_fat_launchd_stdout_leaves_glance_headroom(tmp_path):
    logs = tmp_path / ".lokay" / "logs"
    logs.mkdir(parents=True)
    fat = logs / "launchd-stdout.log"
    fat.write_bytes(b"x" * 8000)
    first = _run_daemon(
        tmp_path,
        extra_env={"LOKAY_LAUNCHD_STDOUT_MAX": "2048"},
    )
    assert first.returncode == 0, first.stderr
    assert fat.stat().st_size <= 2048 - 1024
    assert b"truncated" in fat.read_bytes()
    body = fat.read_bytes()
    second = _run_daemon(
        tmp_path,
        extra_env={"LOKAY_LAUNCHD_STDOUT_MAX": "2048"},
    )
    assert second.returncode == 0, second.stderr
    assert fat.read_bytes() == body


def test_xml_plist_skips_python_launchd_stdout_paths(tmp_path):
    """Missing or XML plist skips python plistlib. Binary plist still python."""
    logs = tmp_path / ".lokay" / "logs"
    logs.mkdir(parents=True)
    custom = logs / "custom-stdout.log"
    custom.write_bytes(b"idle glance" + bytes([10]))
    plist = tmp_path / "job.plist"
    plist.write_text(
        chr(10).join(
            [
                '<?xml version="1.0" encoding="UTF-8"?>',
                '<plist version="1.0">',
                "<dict>",
                "<key>StandardOutPath</key>",
                "<string>" + str(custom) + "</string>",
                "<key>StandardErrorPath</key>",
                "<string>" + str(logs / "custom-stderr.log") + "</string>",
                "</dict>",
                "</plist>",
                "",
            ]
        ),
        encoding="utf-8",
    )
    wrapper = tmp_path / "pywrap"
    log = tmp_path / "pywrap.log"
    wrapper.write_text(
        chr(10).join(
            [
                "#!/bin/sh",
                "printf '%s\\n' \"$*\" >> '" + str(log) + "'",
                'exec /usr/bin/python3 "$@"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    completed = _run_daemon(
        tmp_path,
        extra_env={
            "LOKAY_PYTHON3": str(wrapper),
            "LOKAY_LAUNCHD_PLIST": str(plist),
            "LOKAY_LAUNCHD_STDOUT_MAX": "2048",
        },
    )
    assert completed.returncode == 0, completed.stderr
    assert custom.read_bytes() == b"idle glance" + bytes([10])
    assert log.is_file()
    assert not any(
        line.split()[:2] == ["-", str(plist)] and len(line.split()) >= 4
        for line in log.read_text(encoding="utf-8").splitlines()
    )


def test_xml_plist_stdout_path_still_bounds(tmp_path):
    logs = tmp_path / ".lokay" / "logs"
    logs.mkdir(parents=True)
    custom = logs / "custom-stdout.log"
    custom.write_bytes(b"x" * 8000)
    plist = tmp_path / "job.plist"
    plist.write_text(
        chr(10).join(
            [
                '<?xml version="1.0" encoding="UTF-8"?>',
                '<plist version="1.0">',
                "<dict>",
                "<key>StandardOutPath</key>",
                "<string>" + str(custom) + "</string>",
                "</dict>",
                "</plist>",
                "",
            ]
        ),
        encoding="utf-8",
    )
    completed = _run_daemon(
        tmp_path,
        extra_env={
            "LOKAY_LAUNCHD_PLIST": str(plist),
            "LOKAY_LAUNCHD_STDOUT_MAX": "2048",
        },
    )
    assert completed.returncode == 0, completed.stderr
    assert custom.stat().st_size <= 2048 - 1024
    assert b"truncated" in custom.read_bytes()


def test_mill_logs_under_keep_skip_python_prune(tmp_path):
    logs = tmp_path / ".lokay" / "logs"
    logs.mkdir(parents=True)
    kept = []
    for name in ["mill-20260821T120001Z.log", "mill-20260821T120002Z.log"]:
        path = logs / name
        path.write_text("idle\n", encoding="utf-8")
        kept.append(path)
    completed = _run_daemon(tmp_path, extra_env={"LOKAY_MILL_LOG_KEEP": "48"})
    assert completed.returncode == 0, completed.stderr
    for path in kept:
        assert path.exists()


def test_fresh_idle_skip_defers_mill_log_prune(tmp_path):
    first = _run_daemon(tmp_path)
    assert first.returncode == 0, first.stderr
    lokay = tmp_path / ".lokay"
    (lokay / "last-pass.json").write_text(_idle_receipt(), encoding="utf-8")
    (lokay / "factory-survey.stamp").write_text("1", encoding="utf-8")
    (lokay / "leftover-closeout.stamp").write_text("1", encoding="utf-8")
    logs = lokay / "logs"
    stale = logs / "mill-20260821T110001Z.log"
    stale.write_text("old\n", encoding="utf-8")
    os.utime(stale, (1, 1))
    second = _run_daemon(tmp_path, extra_env={"LOKAY_MILL_LOG_KEEP": "1"})
    assert second.returncode == 0, second.stderr
    assert stale.exists()
    logs_body = chr(10).join(path.read_text(encoding="utf-8") for path in logs.glob("mill-*.log"))
    assert "recent_empty_survey" in logs_body


def test_fresh_idle_skip_defers_first_launchd_stdio_bound(tmp_path):
    first = _run_daemon(tmp_path)
    assert first.returncode == 0, first.stderr
    lokay = tmp_path / ".lokay"
    (lokay / "last-pass.json").write_text(_idle_receipt(), encoding="utf-8")
    (lokay / "factory-survey.stamp").write_text("1", encoding="utf-8")
    (lokay / "leftover-closeout.stamp").write_text("1", encoding="utf-8")
    logs = lokay / "logs"
    fat = logs / "launchd-stdout.log"
    fat.write_bytes(b"x" * 8000)
    second = _run_daemon(tmp_path, extra_env={"LOKAY_LAUNCHD_STDOUT_MAX": "2048"})
    assert second.returncode == 0, second.stderr
    assert fat.stat().st_size == 8000
    logs_body = chr(10).join(path.read_text(encoding="utf-8") for path in logs.glob("mill-*.log"))
    assert "recent_empty_survey" in logs_body


def test_mill_logs_over_keep_still_prune(tmp_path):
    logs = tmp_path / ".lokay" / "logs"
    logs.mkdir(parents=True)
    stale = logs / "mill-20260821T110001Z.log"
    stale.write_text("old\n", encoding="utf-8")
    os.utime(stale, (1, 1))
    for index in range(3):
        path = logs / f"mill-20260821T12000{index}Z.log"
        path.write_text("newer\n", encoding="utf-8")
        os.utime(path, (100 + index, 100 + index))
    completed = _run_daemon(tmp_path, extra_env={"LOKAY_MILL_LOG_KEEP": "2"})
    assert completed.returncode == 0, completed.stderr
    remaining = [
        path
        for path in logs.glob("mill-*.log")
        if path.name != "mill-latest.log"
    ]
    assert len(remaining) == 2
    assert not stale.exists()


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
    remaining = {"by_repo": {"a/b": {"remaining_ready": 0}}}
    receipt.write_text(json.dumps({"remaining": remaining}), encoding="utf-8")

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
    assert out["remaining"] == remaining
    persisted = json.loads(receipt.read_text())
    assert persisted["reason"] == "pass_ceiling"
    assert persisted["remaining"] == remaining


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
