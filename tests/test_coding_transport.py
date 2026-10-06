import json
import os
import signal
import sys
import time

from lokay.coding_boundary import parse_output
from lokay.runner import CommandSpec, Runner


def test_terminal_coding_result_excludes_process_diagnostics():
    expected = {
        "verdict": "implemented",
        "evidence_kind": None,
        "summary": "Changed the requested file.",
        "tests_run": [],
        "residual_risk": "",
    }
    script = (
        "import os, sys\n"
        "assert os.isatty(sys.stdin.fileno())\n"
        "assert os.isatty(sys.stdout.fileno())\n"
        "assert os.isatty(sys.stderr.fileno())\n"
        "print('pi: using classic interface', file=sys.stderr, flush=True)\n"
        f"print({json.dumps(expected)!r}, flush=True)\n"
    )
    result = Runner().run(
        CommandSpec(argv=(sys.executable, "-c", script), pty=True, timeout_seconds=5),
        live=True,
    )
    assert result.returncode == 0
    assert result.stderr.strip() == "pi: using classic interface"
    assert parse_output(result.stdout) == expected


def test_terminal_transport_drains_large_immediate_outputs():
    script = (
        "import os\n"
        "os.write(1, b'o' * (256 * 1024) + b'OUT-TAIL')\n"
        "os.write(2, b'e' * (256 * 1024) + b'ERR-TAIL')\n"
        "os._exit(0)\n"
    )
    result = Runner().run(
        CommandSpec(argv=(sys.executable, "-c", script), pty=True, timeout_seconds=5),
        live=True,
    )
    assert result.returncode == 0
    assert result.stdout == "o" * (256 * 1024) + "OUT-TAIL"
    assert result.stderr == "e" * (256 * 1024) + "ERR-TAIL"


def test_terminal_transport_drains_after_launcher_exits():
    stdout = "o" * (256 * 1024) + "OUT-TAIL"
    stderr = "e" * (256 * 1024) + "ERR-TAIL"
    script = (
        "import os, time\n"
        "if os.fork():\n"
        "    os._exit(0)\n"
        "time.sleep(0.05)\n"
        "os.write(1, b'o' * (256 * 1024) + b'OUT-TAIL')\n"
        "os.write(2, b'e' * (256 * 1024) + b'ERR-TAIL')\n"
        "os._exit(0)\n"
    )
    for _ in range(3):
        result = Runner().run(
            CommandSpec(argv=(sys.executable, "-c", script), pty=True, timeout_seconds=5),
            live=True,
        )
        assert result.returncode == 0
        assert result.stdout == stdout
        assert result.stderr == stderr


def test_terminal_timeout_retains_both_streams():
    script = (
        "import os, time\n"
        "os.write(1, b'result-before-timeout')\n"
        "os.write(2, b'warning-before-timeout')\n"
        "time.sleep(30)\n"
    )
    result = Runner().run(
        CommandSpec(argv=(sys.executable, "-c", script), pty=True, timeout_seconds=1),
        live=True,
    )
    assert result.returncode == 124
    assert result.timed_out is True
    assert result.stdout == "result-before-timeout"
    assert result.stderr == "warning-before-timeout\ntimed out after 1 seconds"


def test_terminal_timeout_keeps_stderr_only_diagnostics():
    script = (
        "import os, time\n"
        "os.write(2, b'warning-only')\n"
        "time.sleep(30)\n"
    )
    result = Runner().run(
        CommandSpec(argv=(sys.executable, "-c", script), pty=True, timeout_seconds=1),
        live=True,
    )
    assert result.returncode == 124
    assert result.timed_out is True
    assert result.stdout == ""
    assert result.stderr == "warning-only\ntimed out after 1 seconds"


def test_terminal_closed_streams_still_enforce_child_timeout():
    script = (
        "import os, time\n"
        "os.write(1, b'result-before-close')\n"
        "os.close(0)\n"
        "os.close(1)\n"
        "os.close(2)\n"
        "time.sleep(2)\n"
    )
    started = time.monotonic()
    result = Runner().run(
        CommandSpec(argv=(sys.executable, "-c", script), pty=True, timeout_seconds=1),
        live=True,
    )
    elapsed = time.monotonic() - started
    assert result.returncode == 124
    assert result.timed_out is True
    assert result.stdout == "result-before-close"
    assert result.stderr == "timed out after 1 seconds"
    assert elapsed < 1.8


def test_terminal_timeout_terminates_invocation_descendant(tmp_path):
    marker = tmp_path / "descendant-survived"
    script = (
        "import os, time\n"
        "pid = os.fork()\n"
        "if pid == 0:\n"
        "    time.sleep(1.5)\n"
        f"    open({str(marker)!r}, 'w').write('survived')\n"
        "    os._exit(0)\n"
        "os.write(1, str(pid).encode())\n"
        "time.sleep(30)\n"
    )
    result = Runner().run(
        CommandSpec(argv=(sys.executable, "-c", script), pty=True, timeout_seconds=1),
        live=True,
    )
    descendant = int(result.stdout)
    try:
        assert result.timed_out is True
        time.sleep(0.7)
        assert not marker.exists()
    finally:
        try:
            os.kill(descendant, signal.SIGKILL)
        except ProcessLookupError:
            pass
