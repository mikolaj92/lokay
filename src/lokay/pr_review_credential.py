"""Resolve the existing Pi provider credential without widening its scope."""

from __future__ import annotations

import os
import selectors
import signal
import subprocess
import time
from pathlib import Path
from typing import Any, Sequence

DEFAULT_PI_COMMAND = (
    "/Users/mini-m4-0/.local/share/mise/installs/pi/0.87.0/pi/pi",
    "auth",
    "print-api-key",
    "--provider",
    "omniroute",
)
_MAX_RESOLVER_OUTPUT_BYTES = 4096
_ALLOWED_ENVIRONMENT = frozenset({"HOME", "PATH", "LANG", "NO_COLOR", "TERM"})


def default_resolver_command() -> tuple[str, ...]:
    """Return the pinned Pi auth command used by production."""
    return DEFAULT_PI_COMMAND


def resolver_home() -> Path:
    """Return the real Pi home, independent of any temporary OCR HOME."""
    return Path.home()


def resolver_command_is_canonical(command: Sequence[str]) -> bool:
    """Check the exact production command without accepting a shell override."""
    return tuple(str(item) for item in command) == default_resolver_command()


def _production_command(command: Sequence[str] | None) -> tuple[str, ...]:
    selected = default_resolver_command() if command is None else command
    try:
        return tuple(str(item) for item in selected)
    except (TypeError, ValueError) as exc:
        raise PiCredentialError("Pi credential resolver command is invalid") from exc


class PiCredentialError(RuntimeError):
    """The configured Pi resolver did not produce one safe credential."""


def _resolver_environment(*, home: Path | None = None) -> dict[str, str]:
    selected_home = home if home is not None else resolver_home()
    return {
        "HOME": str(selected_home),
        "PATH": "/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "NO_COLOR": "1",
        "TERM": "dumb",
    }


def _kill_process_group(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except OSError:
        try:
            process.kill()
        except OSError:
            pass
    try:
        process.wait(timeout=2)
    except (OSError, subprocess.TimeoutExpired):
        pass


def _run_resolver(
    argv: list[str],
    *,
    environment: dict[str, str],
    timeout: float = 10.0,
) -> bytes:
    try:
        process = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=environment,
            start_new_session=True,
            bufsize=0,
        )
    except OSError as exc:
        raise PiCredentialError("Pi credential resolver failed") from exc
    assert process.stdout is not None
    output = bytearray()
    deadline = time.monotonic() + timeout
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise PiCredentialError("Pi credential resolver timed out")
                events = selector.select(min(remaining, 0.25))
                if not events:
                    if process.poll() is not None:
                        break
                    continue
                chunk = os.read(
                    process.stdout.fileno(),
                    min(65536, _MAX_RESOLVER_OUTPUT_BYTES + 1 - len(output)),
                )
                if not chunk:
                    if process.poll() is not None:
                        break
                    continue
                output.extend(chunk)
                if len(output) > _MAX_RESOLVER_OUTPUT_BYTES:
                    raise PiCredentialError(
                        "Pi credential resolver output exceeded size limit"
                    )
        if process.wait(timeout=max(0.1, deadline - time.monotonic())) != 0:
            raise PiCredentialError("Pi credential resolver failed")
        return bytes(output)
    except PiCredentialError:
        _kill_process_group(process)
        raise
    except (OSError, subprocess.TimeoutExpired) as exc:
        _kill_process_group(process)
        raise PiCredentialError("Pi credential resolver failed") from exc


def _run_with_runner(
    runner: Any,
    argv: list[str],
    *,
    environment: dict[str, str],
) -> bytes:
    try:
        completed = runner(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=environment,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PiCredentialError("Pi credential resolver failed") from exc
    stdout = completed.stdout
    if not isinstance(stdout, (bytes, bytearray)):
        raise PiCredentialError("Pi credential resolver returned invalid output")
    if len(stdout) > _MAX_RESOLVER_OUTPUT_BYTES:
        raise PiCredentialError("Pi credential resolver output exceeded size limit")
    if completed.returncode != 0:
        raise PiCredentialError("Pi credential resolver failed")
    return bytes(stdout)


def resolve_pi_api_key(
    *,
    command: Sequence[str] | None = None,
    home: Path | None = None,
    runner: Any | None = None,
) -> str:
    """Resolve Pi's provider key using direct argv and a bounded clean env.

    Production accepts only the pinned ``DEFAULT_PI_COMMAND``. Tests and
    deterministic callers may inject a runner seam for synthetic commands.
    The returned value is intentionally kept in the caller's local scope. This
    function does not modify ``os.environ`` or write a credential-bearing file.
    """
    try:
        argv = _production_command(command)
    except (TypeError, ValueError) as exc:
        raise PiCredentialError("Pi credential resolver command is invalid") from exc
    if not argv or any(not item or "\x00" in item or "\n" in item for item in argv):
        raise PiCredentialError("Pi credential resolver command is invalid")
    if runner is None and not resolver_command_is_canonical(argv):
        raise PiCredentialError("Pi credential resolver command is not canonical")
    if runner is not None and resolver_command_is_canonical(argv):
        # A supplied runner is a test seam, never a production execution path.
        # Keep the canonical command on the real subprocess boundary.
        raise PiCredentialError("Pi credential resolver runner is test-only")
    environment = _resolver_environment(home=home)
    if set(environment) - _ALLOWED_ENVIRONMENT:
        raise PiCredentialError("Pi credential resolver environment is invalid")
    output = (
        _run_with_runner(runner, list(argv), environment=environment)
        if runner is not None
        else _run_resolver(list(argv), environment=environment)
    )
    # The Pi CLI emits one terminal newline. Accept LF or CRLF, but do not
    # silently trim arbitrary trailing whitespace from a credential.
    if output.endswith(b"\r\n"):
        value = output[:-2]
    elif output.endswith(b"\n"):
        value = output[:-1]
    elif output.endswith(b"\r"):
        raise PiCredentialError("Pi credential resolver returned invalid output")
    else:
        value = output
    if not value or b"\x00" in value or b"\n" in value or b"\r" in value:
        raise PiCredentialError("Pi credential resolver returned invalid output")
    try:
        decoded = value.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PiCredentialError("Pi credential resolver returned invalid output") from exc
    if not decoded.strip() or decoded != decoded.strip():
        raise PiCredentialError("Pi credential resolver returned invalid output")
    return decoded
