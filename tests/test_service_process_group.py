"""The real shell launch must isolate the daemon from its caretaker."""

import os
from pathlib import Path
import signal
import subprocess


def test_daemon_launch_has_separate_process_group():
    script = (Path(__file__).resolve().parents[1] / "scripts/lokay-service.sh").read_text()
    launch = script.split("set +e\n", 1)[1].split("DAEMON_PID=$!", 1)[0]
    # Exercise the shell launch mechanics with a real bounded OS process.
    # Product execution is not needed to observe process-group ownership.
    launch = launch.replace(
        'uv run lokay-daemon --config "${CFG}" --max-passes "${LOKAY_MAX_PASSES:-8}" --outbox "${OUTBOX}"',
        "sleep 30",
    )
    shell = subprocess.Popen(
        ["/bin/bash", "-c", launch + 'pid=$!; printf "%s\\n" "$pid"; wait "$pid"'],
        env={**os.environ, "LOG": "/dev/null"},
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
        start_new_session=True,
    )
    child = 0
    try:
        assert shell.stdout is not None
        child = int(shell.stdout.readline())
        assert os.getpgid(child) != os.getpgid(shell.pid)
    finally:
        if child:
            try:
                os.kill(child, signal.SIGTERM)
            except ProcessLookupError:
                pass
        shell.wait(timeout=5)
