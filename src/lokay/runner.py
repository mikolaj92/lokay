from __future__ import annotations

import errno
import os
import pty
import re
import select
import signal
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from lokay.gh_rate import backoff_seconds, is_rate_limit_text
from lokay.process_timeout import run_process
from lokay.safety import validate_argv

# Force machine-readable CLI output. Host shells often export CLICOLOR_FORCE /
# FORCE_COLOR which make modern `gh --json` emit ANSI and break json.loads.
_MACHINE_ENV = {
    "NO_COLOR": "1",
    "CLICOLOR": "0",
    "CLICOLOR_FORCE": "0",
    "FORCE_COLOR": "0",
    "GH_FORCE_TTY": "0",
    "TERM": "dumb",
}

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def strip_ansi(text: str) -> str:
    """Remove ANSI SGR/CSI sequences (defensive if a child still colors)."""
    if not text or "\x1b" not in text:
        return text
    return _ANSI_RE.sub("", text)


@dataclass(frozen=True)
class CommandSpec:
    argv: tuple[str, ...]
    cwd: str | None = None
    env: Mapping[str, str] = field(default_factory=dict)
    timeout_seconds: int = 120
    inherit_env: bool = True
    # pi reads its provider key only when attached to a terminal and hangs
    # forever otherwise. The daemon has no terminal, so those calls opt in.
    pty: bool = False

    def display(self) -> str:
        return " ".join(self.argv)


@dataclass(frozen=True)
class CommandResult:
    spec: CommandSpec
    executed: bool
    returncode: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False


def git_spec(args: Sequence[str], cwd: str | Path | None = None, timeout_seconds: int = 120) -> CommandSpec:
    return CommandSpec(
        argv=("git", *tuple(args)),
        cwd=str(cwd) if cwd else None,
        env={"GIT_TERMINAL_PROMPT": "0"},
        timeout_seconds=timeout_seconds,
    )


def gh_spec(args: Sequence[str], timeout_seconds: int = 120) -> CommandSpec:
    return CommandSpec(argv=("gh", *tuple(args)), timeout_seconds=timeout_seconds)


class Runner:
    def __init__(
        self,
        *,
        gh_retry_max: int = 3,
        sleep_fn=time.sleep,
    ) -> None:
        self.gh_retry_max = max(0, int(gh_retry_max))
        self._sleep = sleep_fn

    def run(self, spec: CommandSpec, *, live: bool) -> CommandResult:
        validate_argv(spec.argv)
        if not live:
            return CommandResult(spec=spec, executed=False, returncode=0)
        env = os.environ.copy() if spec.inherit_env else {}
        env.update(_MACHINE_ENV)
        env.update(spec.env)
        # Command-specific environment must never mutate the long-lived organ.
        # In particular run_agent clears the lease only in the coding harness,
        # while later Fala atoms still need the daemon-issued capability.
        # Spec env must not re-enable forced color for machine parsers.
        env["NO_COLOR"] = "1"
        env["CLICOLOR_FORCE"] = "0"
        env["FORCE_COLOR"] = "0"
        env["GH_FORCE_TTY"] = "0"

        attempts = 1
        if spec.argv and spec.argv[0] == "gh":
            attempts = 1 + self.gh_retry_max

        if spec.pty:
            return _run_pty(spec, env)
        last = CommandResult(spec=spec, executed=True, returncode=1)
        for attempt in range(attempts):
            try:
                completed = run_process(
                    list(spec.argv),
                    cwd=spec.cwd,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=spec.timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                out = exc.stdout or ""
                err = exc.stderr or ""
                if isinstance(out, bytes):
                    out = out.decode("utf-8", errors="replace")
                if isinstance(err, bytes):
                    err = err.decode("utf-8", errors="replace")
                return CommandResult(
                    spec=spec,
                    executed=True,
                    returncode=124,
                    stdout=strip_ansi(out),
                    stderr=strip_ansi(
                        (err + "\n" if err else "")
                        + f"timed out after {spec.timeout_seconds} seconds"
                    ),
                    timed_out=True,
                )
            last = CommandResult(
                spec=spec,
                executed=True,
                returncode=completed.returncode,
                stdout=strip_ansi(completed.stdout or ""),
                stderr=strip_ansi(completed.stderr or ""),
            )
            if last.returncode == 0:
                return last
            if not is_rate_limit_text(last.stdout, last.stderr):
                return last
            if attempt + 1 >= attempts:
                break
            self._sleep(backoff_seconds(attempt))
        return last

    def run_checked(self, spec: CommandSpec, *, live: bool) -> CommandResult:
        result = self.run(spec, live=live)
        if live and result.returncode != 0:
            detail = f"{result.stdout[-2000:]}\n{result.stderr[-2000:]}".strip()
            if is_rate_limit_text(result.stdout, result.stderr):
                raise RuntimeError(
                    f"gh rate limit exhausted after retries ({result.returncode}): "
                    f"{spec.display()}\n{detail}"
                )
            raise RuntimeError(
                f"command failed ({result.returncode}): {spec.display()}\n"
                f"stdout: {result.stdout[-2000:]}\nstderr: {result.stderr[-2000:]}"
            )
        return result


def _run_pty(spec: CommandSpec, env: Mapping[str, str]) -> CommandResult:
    master, slave = pty.openpty()
    diagnostic_master = diagnostic_slave = -1
    proc = None
    try:
        diagnostic_master, diagnostic_slave = pty.openpty()
        proc = subprocess.Popen(
            list(spec.argv), cwd=spec.cwd, env=dict(env),
            stdin=slave, stdout=slave, stderr=diagnostic_slave,
            start_new_session=True,
        )
        os.close(slave)
        slave = -1
        os.close(diagnostic_slave)
        diagnostic_slave = -1
        chunks: dict[int, list[bytes]] = {master: [], diagnostic_master: []}
        active = set(chunks)
        deadline = time.monotonic() + spec.timeout_seconds
        timed_out = False
        while active or proc.poll() is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                if timed_out:
                    break
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                timed_out = True
                deadline = time.monotonic() + 5
                continue
            ready, _, _ = select.select(list(active), [], [], min(remaining, 0.05))
            for fd in ready:
                try:
                    chunk = os.read(fd, 65536)
                except OSError as exc:
                    # Linux PTY masters report EIO when their slaves close.
                    if exc.errno != errno.EIO:
                        raise
                    chunk = b""
                if chunk:
                    chunks[fd].append(chunk)
                else:
                    active.remove(fd)
        proc.wait(timeout=5)
        stderr = b"".join(chunks[diagnostic_master]).decode("utf-8", "replace")
        if timed_out:
            stderr += ("\n" if stderr else "") + f"timed out after {spec.timeout_seconds} seconds"
        return CommandResult(
            spec=spec, executed=True, returncode=124 if timed_out else proc.returncode,
            stdout=strip_ansi(b"".join(chunks[master]).decode("utf-8", "replace")),
            stderr=strip_ansi(stderr), timed_out=timed_out,
        )
    finally:
        try:
            if proc is not None and proc.poll() is None:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait(timeout=5)
        finally:
            for fd in (slave, diagnostic_slave, master, diagnostic_master):
                if fd >= 0:
                    os.close(fd)
