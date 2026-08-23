"""Physical process liveness for detached issue delivery."""

from __future__ import annotations
import os, signal, subprocess, time
from typing import Any


def _terminate_detached_process_group(
    proc: Any, *, timeout_seconds: float = 5.0
) -> bool:
    """Terminate and confirm a child started with ``start_new_session=True`` is gone."""
    try:
        pid = int(proc.pid)
    except (AttributeError, TypeError, ValueError):
        return False
    if pid <= 0:
        return False

    def gone() -> bool:
        try:
            os.killpg(pid, 0)
        except ProcessLookupError:
            return True
        except OSError:
            return False
        return False

    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    except OSError:
        return False
    deadline = time.monotonic() + max(0.0, timeout_seconds)
    while time.monotonic() < deadline:
        if gone():
            return True
        time.sleep(0.05)
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        return True
    except OSError:
        return False
    deadline = time.monotonic() + max(0.0, timeout_seconds)
    while time.monotonic() < deadline:
        if gone():
            return True
        time.sleep(0.05)
    return gone()


def terminate_issue_to_pr_pid(pid: int, *, timeout_seconds: float = 5.0) -> bool:
    """Kill a detached issue_to_pr session by pid (same as the spawn helper)."""

    class _Proc:
        def __init__(self, value: int) -> None:
            self.pid = int(value)

    return _terminate_detached_process_group(
        _Proc(pid), timeout_seconds=timeout_seconds
    )


def pid_is_alive(pid: int) -> bool:
    if int(pid) <= 0:
        return False
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        # An indeterminate liveness probe must not make an existing detached
        # receipt disappear from occupancy or destructive-reap protection.
        return True
    return True


def _pid_command(pid: int) -> str:
    try:
        done = subprocess.run(
            ["ps", "-ww", "-p", str(int(pid)), "-o", "command="],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return (done.stdout or "").strip()


def is_coding_command(command: str) -> bool:
    """True for the i2pr wrapper or the Fala/pi coder it spawned."""
    if "lokay.compose.issue_to_pr" in command or "lokay-issue-to-pr" in command:
        return True
    if "lokay.fala_organ" in command:
        return True
    return "implement GitHub issue #" in command


def _child_pids(pid: int) -> list[int]:
    try:
        done = subprocess.run(
            ["pgrep", "-P", str(int(pid))],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    out: list[int] = []
    for line in (done.stdout or "").splitlines():
        try:
            child = int(line.strip())
        except ValueError:
            continue
        if child > 0:
            out.append(child)
    return out


def wrapper_has_coding_descendant(
    pid: int,
    *,
    command_of=None,
    children_of=None,
) -> bool:
    """True when the detached wrapper still has a Fala/pi coder under it."""
    command_of = command_of or _pid_command
    children_of = children_of or _child_pids
    seen: set[int] = set()
    stack = [int(pid)]
    while stack:
        cur = stack.pop()
        if cur in seen or cur <= 0:
            continue
        seen.add(cur)
        if cur != int(pid) and is_coding_command(command_of(cur)):
            return True
        stack.extend(children_of(cur))
    return False


def coding_live_for_issue(issue: int) -> bool:
    """Orphan coder still writing this ticket after the wrapper died."""
    needle = f"implement GitHub issue #{int(issue)}"
    try:
        done = subprocess.run(
            ["pgrep", "-f", needle],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return bool((done.stdout or "").strip())


def is_live_issue_to_pr_pid(pid: int) -> bool:
    if not pid_is_alive(pid):
        return False
    command = _pid_command(pid)
    # A live PID whose command cannot be read is unknown, not dead. Keep its
    # receipt as occupancy so neither dispatch nor stale-worktree reap can race
    # a coding child. A readable non-Lokay command still rejects PID reuse.
    if not command:
        return True
    if is_coding_command(command):
        return True
    return wrapper_has_coding_descendant(pid)
