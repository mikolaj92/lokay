"""Atomic repo-scoped flock: acquire at launch, observe without mutate, recover on death."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from lokay.proc.repo_lock import (
    acquire_repo_lock,
    inspect_repo_lock,
    repo_lock_dir,
    repo_lock_path,
)


def test_lock_identity_is_scoped_by_state_dir_and_repo(tmp_path):
    a = repo_lock_path(tmp_path / "state-a", "mikolaj92/lokay")
    b = repo_lock_path(tmp_path / "state-a", "mikolaj92/reviewkit")
    c = repo_lock_path(tmp_path / "state-b", "mikolaj92/lokay")
    assert a != b
    assert a != c
    assert a.parent == tmp_path / "state-a" / "repo-locks"
    assert a.name == "mikolaj92__lokay.lock"


def test_configured_lock_dir_follows_state_path(tmp_path, monkeypatch):
    monkeypatch.delenv("LOKAY_CONFIG", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    cfg = tmp_path / "config.yaml"
    state = tmp_path / "custom-state" / "events.jsonl"
    state.parent.mkdir()
    cfg.write_text(
        "mode: dry-run\n"
        "repos:\n"
        "  - name: a/b\n"
        f"    clone_path: {tmp_path}\n"
        "executor:\n"
        "  enabled: false\n"
        "  command: true\n"
        '  args: ["{prompt}"]\n'
        "state:\n"
        f"  path: {state}\n",
        encoding="utf-8",
    )
    assert repo_lock_dir(str(cfg)) == state.parent / "repo-locks"
    assert repo_lock_dir(None) == Path(tmp_path / "home") / ".lokay" / "repo-locks"


def test_competing_launchers_cannot_both_acquire(tmp_path):
    path = repo_lock_path(tmp_path, "mikolaj92/lokay")
    first = acquire_repo_lock(path)
    assert first is not None
    second = acquire_repo_lock(path)
    assert second is None
    first.close()
    third = acquire_repo_lock(path)
    assert third is not None
    third.close()


def test_inspect_does_not_acquire_or_unlink(tmp_path):
    path = repo_lock_path(tmp_path, "mikolaj92/lokay")
    assert inspect_repo_lock(path) == {"ok": True, "busy": False, "path": str(path)}
    held = acquire_repo_lock(path)
    assert held is not None
    observed = inspect_repo_lock(path)
    assert observed["busy"] is True
    assert observed["path"] == str(path)
    assert path.is_file()
    held.close()
    assert inspect_repo_lock(path)["busy"] is False
    assert path.is_file()


def test_process_death_releases_lock_without_unlink(tmp_path):
    path = repo_lock_path(tmp_path, "mikolaj92/lokay")
    marker = tmp_path / "held"
    child = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import sys,time; from pathlib import Path;"
                "from lokay.proc.repo_lock import acquire_repo_lock, repo_lock_path;"
                "h=acquire_repo_lock(repo_lock_path(Path(sys.argv[1]), 'mikolaj92/lokay'));"
                "assert h is not None;"
                "Path(sys.argv[2]).write_text('held');"
                "time.sleep(30)"
            ),
            str(tmp_path),
            str(marker),
        ],
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    try:
        deadline = time.monotonic() + 5
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert marker.exists()
        assert inspect_repo_lock(path)["busy"] is True
        assert acquire_repo_lock(path) is None
        child.send_signal(signal.SIGKILL)
        child.wait(timeout=5)
        deadline = time.monotonic() + 5
        while inspect_repo_lock(path)["busy"] and time.monotonic() < deadline:
            time.sleep(0.02)
        assert inspect_repo_lock(path)["busy"] is False
        recovered = acquire_repo_lock(path)
        assert recovered is not None
        recovered.close()
        assert path.is_file()
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)


def test_inspect_implementation_mutex_uses_flock_not_ps(tmp_path, monkeypatch):
    from lokay.proc.inspect_implementation_mutex import inspect

    monkeypatch.setenv("HOME", str(tmp_path))
    candidate = {"ok": True, "route": "candidate", "repo": "mikolaj92/lokay", "issue": 1}
    free = inspect(candidate, config_path=None)
    assert free["route"] == "free"
    assert free["reason"] == "free"
    path = repo_lock_path(tmp_path / ".lokay", "mikolaj92/lokay")
    held = acquire_repo_lock(path)
    assert held is not None
    try:
        busy = inspect(candidate, config_path=None)
        assert busy["route"] == "keep"
        assert busy["reason"] == "busy"
        assert busy["lock"] == str(path)
    finally:
        held.close()


def test_detach_acquires_lock_before_spawn_and_hands_fd(tmp_path, monkeypatch):
    import lokay.proc.issue_delivery_launch as launch

    monkeypatch.setenv("HOME", str(tmp_path))
    seen = {}

    class FakePopen:
        def __init__(self, argv, **kwargs):
            seen["pass_fds"] = kwargs.get("pass_fds")
            seen["env"] = kwargs.get("env") or {}
            self.pid = 4242

    out = launch.detach_issue_to_pr(
        repo="mikolaj92/lokay", issue=9, config_path=None, popen=FakePopen
    )
    assert out["ok"] is True
    assert seen["env"].get("LOKAY_REPO_LOCK_FD")
    fds = seen["pass_fds"]
    assert fds is not None and len(fds) == 2
    lock_fd = int(seen["env"]["LOKAY_REPO_LOCK_FD"])
    assert lock_fd in fds
    lock_path = Path(out["repo_lock"])
    assert lock_path.name == "mikolaj92__lokay.lock"
    assert lock_path.is_file()


def test_second_detach_loses_the_held_repo_lock(tmp_path, monkeypatch):
    import lokay.proc.issue_delivery_launch as launch
    from lokay.proc.launch_issue_to_pr import launch as dispatch_launch

    monkeypatch.setenv("HOME", str(tmp_path))
    path = repo_lock_path(tmp_path / ".lokay", "mikolaj92/lokay")
    held = acquire_repo_lock(path)
    assert held is not None
    try:

        class Boom:
            def __init__(self, *args, **kwargs):
                raise AssertionError("must not spawn while repo lock is held")

        out = launch.detach_issue_to_pr(
            repo="mikolaj92/lokay", issue=9, config_path=None, popen=Boom
        )
        assert out["ok"] is False
        assert out["reason"] == "repo_lock_busy"
        dispatched = dispatch_launch(
            {"ok": True, "route": "do", "repo": "mikolaj92/lokay", "issue": 9},
            config_path=None,
        )
        assert dispatched["route"] == "busy"
        assert dispatched["launch"]["reason"] == "repo_lock_busy"
    finally:
        held.close()


def test_child_holds_inherited_lock_until_exit(tmp_path, monkeypatch):
    import lokay.proc.issue_delivery_launch as launch

    monkeypatch.setenv("HOME", str(tmp_path))
    child_script = tmp_path / "holder.py"
    child_script.write_text(
        "import os,time\n"
        "fd=int(os.environ['LOKAY_REPO_LOCK_FD'])\n"
        "os.read(int(os.environ['LOKAY_ISSUE_TO_PR_ACTIVATION_FD']), 1)\n"
        "open(os.environ['LOKAY_LOCK_MARKER'], 'w').write('held')\n"
        "time.sleep(30)\n",
        encoding="utf-8",
    )
    marker = tmp_path / "held"

    def popen(argv, **kwargs):
        env = dict(kwargs.get("env") or {})
        env["LOKAY_LOCK_MARKER"] = str(marker)
        return subprocess.Popen(
            [sys.executable, "-u", str(child_script)],
            cwd=kwargs.get("cwd"),
            env=env,
            start_new_session=True,
            stdout=kwargs.get("stdout"),
            stderr=kwargs.get("stderr"),
            pass_fds=kwargs.get("pass_fds"),
        )

    out = launch.detach_issue_to_pr(
        repo="mikolaj92/lokay", issue=3, config_path=None, popen=popen
    )
    try:
        assert out["ok"] is True
        pid = int(out["pid"])
        deadline = time.monotonic() + 5
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert marker.exists()
        path = Path(out["repo_lock"])
        assert inspect_repo_lock(path)["busy"] is True
        assert acquire_repo_lock(path) is None
        os.kill(pid, signal.SIGKILL)
        deadline = time.monotonic() + 5
        while inspect_repo_lock(path)["busy"] and time.monotonic() < deadline:
            time.sleep(0.02)
        recovered = acquire_repo_lock(path)
        assert recovered is not None
        recovered.close()
        assert path.is_file()
    finally:
        try:
            os.kill(int(out["pid"]), signal.SIGKILL)
        except (OSError, KeyError, ValueError):
            pass
