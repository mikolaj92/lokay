"""Stopping the caretaker must stop its isolated daemon, not orphan it."""
import os
import signal
import subprocess
import time
from pathlib import Path


def test_service_term_stops_daemon(tmp_path):
    root = Path(__file__).resolve().parents[1]
    pidfile = tmp_path / "daemon.pid"
    bindir = tmp_path / "bin"
    bindir.mkdir()
    uv = bindir / "uv"
    uv.write_text(f'''#!/bin/bash
if [[ "$*" == *"lokay-daemon"* ]]; then
  echo $$ > '{pidfile}'
  exec sleep 30
fi
if [[ "$*" == *"stop_cycle_tree"* ]]; then
  kill -TERM "$5" 2>/dev/null || true
fi
''')
    uv.chmod(0o755)
    config = tmp_path / "config.yaml"
    config.write_text("mode: live\n")
    env = {**os.environ, "HOME": str(tmp_path), "PATH": f"{bindir}:/usr/bin:/bin",
           "LOKAY_ROOT": str(root), "LOKAY_CONFIG": str(config),
           "LOKAY_PASS_CEILING_SECONDS": "30", "GH_TOKEN": "test"}
    shell = subprocess.Popen(["/bin/bash", str(root / "scripts/lokay-service.sh")], env=env,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    daemon = 0
    try:
        deadline = time.monotonic() + 5
        while not pidfile.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert pidfile.exists()
        daemon = int(pidfile.read_text())
        shell.send_signal(signal.SIGTERM)
        shell.wait(timeout=5)
        deadline = time.monotonic() + 2
        alive = True
        while time.monotonic() < deadline:
            try:
                os.kill(daemon, 0)
            except ProcessLookupError:
                alive = False
                break
            time.sleep(0.02)
        assert not alive, "caretaker left its daemon alive after SIGTERM"
    finally:
        for pid in (daemon, shell.pid):
            if pid:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        shell.wait(timeout=5)
