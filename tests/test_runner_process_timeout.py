"""A timed-out command must not leave its ordinary children running."""

import os
import signal
import subprocess
import time

from lokay.runner import CommandSpec, Runner


def test_timeout_stops_child_and_preserves_output(tmp_path):
    pidfile = tmp_path / "child.pid"
    script = tmp_path / "parent.sh"
    script.write_text('sleep 60 &\nprintf "%s" "$!" > "$1"\nprintf "started\\n"\nwait\n')
    try:
        result = Runner().run(
            CommandSpec(("bash", str(script), str(pidfile)), timeout_seconds=1),
            live=True,
        )
        assert result.timed_out and result.returncode == 124
        assert "started" in result.stdout
        assert pidfile.exists(), "parent did not start child"
        pid = int(pidfile.read_text())
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            probe = subprocess.run(["ps", "-p", str(pid), "-o", "stat="], capture_output=True, text=True)
            if not probe.stdout.strip() or probe.stdout.strip().startswith("Z"):
                break
            time.sleep(0.05)
        else:
            raise AssertionError(f"timeout left child {pid} alive")
    finally:
        if pidfile.exists():
            try:
                os.kill(int(pidfile.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass
