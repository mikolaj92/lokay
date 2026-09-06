"""Bound one command and its ordinary descendants to the same lifetime."""

import os
import signal
import subprocess


def run_process(argv, *, cwd, env, capture_output, text, timeout, check):
    with subprocess.Popen(
        argv,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE if capture_output else None,
        stderr=subprocess.PIPE if capture_output else None,
        text=text,
        start_new_session=True,
    ) as process:
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            # Killing only the launcher (e.g. uv) leaves pytest alive. The
            # session belongs to this invocation, never to its caretaker.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout, stderr = process.communicate(timeout=5)
            raise subprocess.TimeoutExpired(argv, timeout, output=stdout, stderr=stderr)
        result = subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)
        if check:
            result.check_returncode()
        return result
