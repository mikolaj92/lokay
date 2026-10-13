from __future__ import annotations

import math
import os
import signal
import subprocess
import time
from contextvars import ContextVar
from collections.abc import Mapping, Sequence
from pathlib import Path


class TickExpired(BaseException):
    """Yield to the next tick without treating the saved node as failed."""


tick_deadline: ContextVar[float | None] = ContextVar("tick_deadline", default=None)


def check_deadline() -> None:
    deadline = tick_deadline.get()
    if deadline is not None and time.monotonic() >= deadline:
        raise TickExpired()


def retry_sleep(seconds: float) -> None:
    check_deadline()
    deadline = tick_deadline.get()
    time.sleep(seconds if deadline is None else min(seconds, max(0, deadline - time.monotonic())))
    check_deadline()


def run_process(
    argv: Sequence[str],
    *,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    # Even callers without a timeout cannot hold a tick indefinitely.
    timeout = 3600 if timeout is None else timeout
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("process timeout must be finite and positive")
    timeout = min(timeout, 3600)
    deadline = tick_deadline.get()
    remaining = None if deadline is None else deadline - time.monotonic()
    if remaining is not None and remaining <= 0:
        raise TickExpired()
    tick_limited = remaining is not None and remaining <= timeout
    effective_timeout = timeout if remaining is None else min(timeout, remaining)
    process = subprocess.Popen(
        list(argv),
        cwd=cwd,
        env=None if env is None else dict(env),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        try:
            stdout, stderr = process.communicate(timeout=effective_timeout)
        except subprocess.TimeoutExpired as error:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                stdout, stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired as drain_error:
                stdout = drain_error.output if drain_error.output is not None else error.output
                stderr = drain_error.stderr if drain_error.stderr is not None else error.stderr
            if tick_limited:
                raise TickExpired() from None
            raise subprocess.TimeoutExpired(list(argv), timeout, output=stdout, stderr=stderr) from None
        return subprocess.CompletedProcess(list(argv), process.returncode or 0, stdout, stderr)
    finally:
        # Popen.__exit__ waits without a limit, even if draining pipes timed out.
        for stream in (process.stdout, process.stderr):
            if stream is not None:
                stream.close()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
