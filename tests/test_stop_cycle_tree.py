"""Watchdog keeps only registered detached workers, not nested Fala sessions."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from lokay.proc.stop_cycle_tree import cycle_targets, registered_worker_pgid, stop


def _sleep(*, start_new_session: bool) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        start_new_session=start_new_session,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _alive(pid: int) -> bool:
    try:
        out = subprocess.run(
            ["ps", "-p", str(pid), "-o", "stat="],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return False
    stat = (out.stdout or "").strip()
    return bool(stat) and not stat.startswith("Z")


def _wait_dead(pid: int, *, timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _alive(pid):
            return True
        time.sleep(0.05)
    return not _alive(pid)


def _spawn_owner_with_nested() -> tuple[subprocess.Popen, int]:
    owner = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import subprocess, sys, time;"
            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], start_new_session=True);"
            "print(child.pid, flush=True);"
            "time.sleep(30)",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        start_new_session=True,
    )
    nested_pid = int(owner.stdout.readline())
    return owner, nested_pid


def test_nested_fala_session_is_not_a_registered_worker(tmp_path: Path):
    worker = _sleep(start_new_session=True)
    owner = None
    nested_pid = 0
    try:
        cycle = tmp_path / "cycle"
        cycle.mkdir()
        (cycle / "owner.json").write_text(
            json.dumps(
                {
                    "ok": True,
                    "detached": True,
                    "pid": worker.pid,
                    "repo": "owner/repo",
                    "issue": 1,
                }
            ),
            encoding="utf-8",
        )
        owner, nested_pid = _spawn_owner_with_nested()
        assert os.getpgid(worker.pid) in registered_worker_pgid(cycle)
        assert os.getpgid(nested_pid) not in registered_worker_pgid(cycle)
        targets = cycle_targets(owner.pid, cycle)
        assert os.getpgid(nested_pid) in targets
        assert os.getpgid(owner.pid) in targets
        assert os.getpgid(worker.pid) not in targets
    finally:
        for pid in (worker.pid, nested_pid, getattr(owner, "pid", 0)):
            if not pid:
                continue
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except OSError:
                pass
        worker.wait(timeout=2)
        if owner is not None:
            owner.kill()
            owner.wait(timeout=2)


def test_stop_kills_unregistered_session_and_keeps_registered_worker(tmp_path: Path):
    worker = _sleep(start_new_session=True)
    owner = None
    nested_pid = 0
    try:
        cycle = tmp_path / "cycle"
        cycle.mkdir()
        (cycle / "owner.json").write_text(
            json.dumps(
                {
                    "ok": True,
                    "detached": True,
                    "pid": worker.pid,
                    "repo": "owner/repo",
                    "issue": 1,
                }
            ),
            encoding="utf-8",
        )
        owner, nested_pid = _spawn_owner_with_nested()
        stop(owner.pid, cycle, grace_seconds=0.5)
        assert _wait_dead(owner.pid)
        assert _wait_dead(nested_pid)
        assert _alive(worker.pid)
    finally:
        for pid in (worker.pid, nested_pid, getattr(owner, "pid", 0)):
            if not pid:
                continue
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except OSError:
                pass
        worker.wait(timeout=2)
        if owner is not None:
            owner.kill()
            owner.wait(timeout=2)
