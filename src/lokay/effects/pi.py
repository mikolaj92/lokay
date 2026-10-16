from __future__ import annotations

import json
import math
import re
import shutil
import os
import selectors
import sys
import signal
import subprocess
import tempfile
import time
from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from subprocess import TimeoutExpired
from typing import Any, BinaryIO, cast

from lokay import store


PI_IDLE_SECONDS = 300

process_groups: dict[int, subprocess.Popen | None] = {}


def save_process_groups() -> None:
    store.save_process_groups(sorted(process_groups))


def kill_process_groups(pgids: Sequence[int]) -> None:
    pending = set(pgids)
    deadline = time.monotonic() + 3
    for pgid in pending:
        try:
            os.killpg(pgid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
    while pending and time.monotonic() < deadline:
        for pgid in tuple(pending):
            process = process_groups.get(pgid)
            if process is not None:
                process.poll()
            try:
                os.killpg(pgid, 0)
            except (ProcessLookupError, PermissionError):
                pending.remove(pgid)
        if pending:
            time.sleep(0.05)
    for pgid in pending:
        try:
            os.killpg(pgid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    for pgid in pgids:
        process_groups.pop(pgid, None)
    save_process_groups()


def cleanup_process_groups() -> None:
    path = store.process_groups_path()
    if path.exists():
        saved = json.loads(path.read_text())
        if not isinstance(saved, list) or any(type(pgid) is not int or pgid <= 1 or pgid == os.getpgrp() for pgid in saved):
            raise ValueError("invalid process group registry")
        for pgid in saved:
            process_groups.setdefault(pgid, None)
    kill_process_groups(list(process_groups))


def cleanup_worktree_caches(worktree: Path) -> None:
    from lokay.effects.git import command

    token = tick_deadline.set(None)
    try:
        for name in (".cache", ".validation"):
            directory = worktree / name
            if directory.is_symlink() or not directory.is_dir():
                continue
            tracked = command(worktree, ["ls-files", "-z", "--", name])
            if tracked.returncode != 0:
                raise RuntimeError(tracked.stderr or "tracked cache lookup failed")
            if tracked.stdout:
                continue
            ignored = command(worktree, ["check-ignore", "-q", "--", name + "/"])
            if ignored.returncode == 0:
                shutil.rmtree(directory)
            elif ignored.returncode != 1:
                raise RuntimeError(ignored.stderr or "ignored cache lookup failed")
    finally:
        tick_deadline.reset(token)


def pi_env(base: Mapping[str, str], worktree: str | Path) -> dict[str, str]:
    env = dict(base)
    for key in ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN",
                "GIT_ASKPASS", "SSH_AUTH_SOCK"):
        env.pop(key, None)
    env.update({
        "GH_CONFIG_DIR": tempfile.mkdtemp(dir=os.path.realpath(env.get("TMPDIR") or "/tmp")),
        "UV_CACHE_DIR": str(Path(env.get("HOME") or Path.home()) / ".cache" / "uv"),
        "PATH": str(Path(__file__).resolve().parents[3] / "sandbox/bin") + os.pathsep + env.get("PATH", os.defpath),
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_COUNT": "2",
        "GIT_CONFIG_KEY_0": "credential.helper",
        "GIT_CONFIG_VALUE_0": "",
        "GIT_CONFIG_KEY_1": "remote.origin.pushurl",
        "GIT_CONFIG_VALUE_1": "no_push://disabled",
    })
    return env


def sandboxed(argv: list[str], worktree: str | Path, env: Mapping[str, str], extra_dir: str | Path | None = None) -> list[str]:
    if not Path("/usr/bin/sandbox-exec").exists():
        return argv
    worktree = Path(worktree).resolve()
    from lokay.effects.git import command

    git = command(worktree, ["rev-parse", "--git-common-dir"])
    gitdir = (worktree / git.stdout.strip()).resolve() if git.returncode == 0 else worktree
    return [
        "/usr/bin/sandbox-exec", "-f", str(Path(__file__).resolve().parents[3] / "sandbox/pi.sb"),
        "-D", f"WORKTREE={worktree}", "-D", f"GITDIR={gitdir}",
        "-D", f"ARTIFACT_DIR={Path(extra_dir).resolve() if extra_dir is not None else worktree}",
        "-D", f"TMPDIR={os.path.realpath(env.get('TMPDIR') or '/tmp')}",
        "-D", f"HOME={os.path.realpath(env.get('HOME') or os.environ['HOME'])}",
        *argv,
    ]


class TickExpired(BaseException):
    pass


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


def pi_command(argv: Sequence[str]) -> int | None:
    return next((index for index, arg in enumerate(argv)
                 if Path(arg).name == "pi" and "-p" in argv[index + 1:]), None)


def pi_assistant_text(stdout: str) -> str:
    text = None
    try:
        for line in stdout.split("\n"):
            if not line.strip():
                continue
            event = json.loads(line)
            if event.get("type") != "message_end":
                continue
            message = event["message"]
            if message.get("role") == "assistant":
                text = "".join(block["text"] for block in message["content"] if block["type"] == "text")
    except (ValueError, KeyError, TypeError, AttributeError):
        return stdout
    return stdout if text is None else text


def transient_error(proc: subprocess.CompletedProcess[str], transport: str) -> bool:
    statuses = []
    messages = []
    if transport == "curl":
        status = proc.stdout.rpartition("\n")[2].strip()
        if status.isdecimal() and len(status) == 3:
            statuses.append(int(status))
        if proc.returncode == 52:
            messages.append("curl: (52) Empty reply")
    else:
        if proc.returncode == 0:
            return False
        messages.extend(proc.stderr.splitlines())
        if transport == "pi":
            for line in proc.stdout.splitlines():
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(event, dict):
                    continue
                message = event.get("message", event)
                if isinstance(message, dict) and message.get("role", "assistant") == "assistant":
                    error = message.get("errorMessage")
                    if isinstance(error, str):
                        messages.extend(error.splitlines())
                    for key in ("status", "statusCode"):
                        value = message.get(key)
                        if type(value) is int:
                            statuses.append(value)
        for message in messages:
            statuses.extend(int(match) for match in re.findall(
                r"(?i)\b(?:HTTP(?:/\d(?:\.\d)?)?|status(?:\s+code)?)[\s:=]+([1-5]\d\d)\b", message))
            if transport == "pi":
                match = re.match(r"^(?:Error:\s*)?([1-5]\d\d)\b", message)
                if match:
                    statuses.append(int(match[1]))
    if any(status in (401, 403) for status in statuses):
        return False
    return (any(status in (408, 429) or 500 <= status <= 599 for status in statuses)
            or any(re.match(r"^curl: \(52\)", message) for message in messages)
            or transport == "gh" and any(message.startswith("GraphQL: Something went wrong") for message in messages))


def run_process(
    argv: Sequence[str],
    *,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float | None = None,
    input: str | None = None,
    retry: str | None = None,
    reconcile: Callable[[], subprocess.CompletedProcess[str] | None] | None = None,
) -> subprocess.CompletedProcess[str]:
    for attempt in range(4):
        proc = _logged_process(argv, cwd=cwd, env=env, timeout=timeout, input=input)
        if retry is None or not transient_error(proc, retry):
            if pi_command(argv) is not None:
                proc.stdout = pi_assistant_text(proc.stdout)
            return proc
        if reconcile is not None:
            try:
                resolved = reconcile()
            except (RuntimeError, ValueError, TypeError, KeyError, OSError, subprocess.TimeoutExpired):
                return proc
            if resolved is not None:
                return resolved
        if attempt == 3:
            if pi_command(argv) is not None:
                proc.stdout = pi_assistant_text(proc.stdout)
            return proc
        retry_sleep(2 ** attempt)
    return proc


def _logged_process(
    argv: Sequence[str],
    *,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float | None = None,
    input: str | None = None,
) -> subprocess.CompletedProcess[str]:
    from lokay.store import log_event

    command = next((index for index, arg in enumerate(argv)
                    if Path(arg).name == "gh" or (Path(arg).name == "pi" and "-p" in argv[index + 1:])), None)
    if command is None:
        return _run_process(argv, cwd=cwd, env=env, timeout=timeout, input=input)
    call = Path(argv[command]).name
    started = time.monotonic()
    output = None
    ok = False
    try:
        from lokay.effects.git import pi_git_guard

        with pi_git_guard(Path(cwd) if cwd is not None else Path.cwd()) if call == "pi" else nullcontext():
            proc = _run_process(argv, cwd=cwd, env=env, timeout=timeout, input=input)
        output = {"stdout": proc.stdout, "stderr": proc.stderr, "returncode": proc.returncode}
        ok = proc.returncode == 0
        return proc
    except BaseException as exc:
        output = {"error": type(exc).__name__, "reason": str(exc)}
        raise
    finally:
        log_event("call", call=call, name=" ".join(argv[command + 1:command + 3])[:200] if call == "gh" else "pi -p",
                  input={"argv": list(argv[command:]), "stdin": input},
                  output=output, started=started, ok=ok)


def _pi_pids(expires: float) -> set[int]:
    proc = subprocess.run(["ps", "-ww", "-axo", "pid=,comm=,args="], capture_output=True,
                          text=True, timeout=max(0.001, expires - time.monotonic()), check=True)
    pids = set()
    for line in proc.stdout.splitlines():
        row = line.strip().split(None, 2)
        if len(row) < 3:
            continue
        pid, executable, command = row
        args = command.split()
        name = Path(executable).name
        if "-p" not in args[1:]:
            continue
        if not pid.isdecimal() or not args:
            continue
        native = Path(args[0]).name == "pi" and name not in ("sh", "bash", "zsh", "dash", "env")
        node = name in ("node", "nodejs") and len(args) > 1 and (
            Path(args[1]).name == "pi" or (
                Path(args[1]).name in ("cli.js", "cli.mjs", "index.js")
                and ("/pi/" in args[1] or "pi-coding-agent/" in args[1])))
        if native or node:
            pids.add(int(pid))
    return pids


@contextmanager
def _pi_admission(argv, env, expires, expired):
    if pi_command(argv) is None:
        yield
        return
    child = os.environ if env is None else env
    workers = child.get("LOKAY2_WORKERS", "2")
    if workers not in ("1", "2", "3"):
        raise ValueError("LOKAY2_WORKERS must be 1, 2 or 3")
    idle = None
    while True:
        check_deadline()
        if time.monotonic() >= expires:
            expired()
        held = None
        reason = "disk"
        if shutil.disk_usage(Path.home()).free >= 5000000000:
            reason = "pi_capacity"
            held = store.acquire_lock(Path.home() / ".lokay" / "pi-admission.lock")
            if held["result"] == "held":
                try:
                    admitted = len(_pi_pids(expires)) < int(workers)
                except Exception:
                    admitted = False
                if admitted:
                    try:
                        if time.monotonic() >= expires:
                            expired()
                        if idle is not None:
                            from lokay.observe import current

                            current(idle_reason=None)
                        yield
                    finally:
                        store.release_lock(held)
                    return
                store.release_lock(held)
        if idle != reason:
            from lokay.observe import current

            current(idle_reason=reason)
            print(f"idle {reason}", file=sys.stderr, flush=True)
            store.log_event("idle", reason=reason)
            idle = reason
        time.sleep(min(1, max(0, expires - time.monotonic())))


@contextmanager
def _process(argv, cwd, env, input, *, text=False, expires=None, expired=None):
    process: subprocess.Popen[Any] | None = None
    try:
        with _pi_admission(argv, env, expires, expired):
            blocked = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT})
            try:
                process = subprocess.Popen(
                    list(argv),
                    cwd=cwd,
                    env=None if env is None else dict(env),
                    stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=text,
                    start_new_session=True,
                    preexec_fn=lambda: signal.pthread_sigmask(signal.SIG_SETMASK, blocked),
                )
                process_groups[process.pid] = process
                save_process_groups()
            finally:
                signal.pthread_sigmask(signal.SIG_SETMASK, blocked)
            assert process is not None
            if pi_command(argv) is not None:
                assert expires is not None and expired is not None
                while process.poll() is None:
                    check_deadline()
                    if time.monotonic() >= expires:
                        expired()
                    try:
                        if process.pid in _pi_pids(expires):
                            break
                    except Exception:
                        pass
                    time.sleep(min(0.05, max(0, expires - time.monotonic())))
        assert process is not None
        yield process
    finally:
        if process is not None:
            try:
                if process.pid in process_groups:
                    kill_process_groups([process.pid])
                process.wait(timeout=5)
            finally:
                for stream in (process.stdin, process.stdout, process.stderr):
                    if stream is not None:
                        stream.close()


def _run_process(
    argv: Sequence[str],
    *,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float | None = None,
    input: str | None = None,
) -> subprocess.CompletedProcess[str]:
    timeout = 3600 if timeout is None else timeout
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("process timeout must be finite and positive")
    timeout = min(timeout, 3600)
    deadline = tick_deadline.get()
    remaining = None if deadline is None else deadline - time.monotonic()
    if remaining is not None and remaining <= 0:
        raise TickExpired()
    if pi_command(argv) is not None:
        return _run_pi_process(argv, cwd=cwd, env=env, timeout=timeout, input=input)
    with _process(argv, cwd, env, input, text=True) as process:
        remaining = None if deadline is None else max(0, deadline - time.monotonic())
        tick_limited = remaining is not None and remaining <= timeout
        effective_timeout = timeout if remaining is None else min(timeout, remaining)
        try:
            if input is None:
                stdout, stderr = process.communicate(timeout=effective_timeout)
            else:
                stdout, stderr = process.communicate(input=input, timeout=effective_timeout)
        except subprocess.TimeoutExpired as error:
            kill_process_groups([process.pid])
            try:
                stdout, stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired as drain_error:
                stdout = drain_error.output if drain_error.output is not None else error.output
                stderr = drain_error.stderr if drain_error.stderr is not None else error.stderr
            if tick_limited:
                raise TickExpired() from None
            raise subprocess.TimeoutExpired(list(argv), timeout, output=stdout, stderr=stderr) from None
        return subprocess.CompletedProcess(list(argv), process.returncode or 0, stdout, stderr)


def _run_pi_process(
    argv: Sequence[str],
    *,
    cwd: str | Path | None,
    env: Mapping[str, str] | None,
    timeout: float,
    input: str | None,
) -> subprocess.CompletedProcess[str]:
    from lokay.store import log_event

    argv = list(argv)
    command = pi_command(argv)
    assert command is not None
    if "--mode" in argv[command + 1:]:
        mode = argv.index("--mode", command + 1)
        argv[mode + 1:mode + 2] = ["json"]
    else:
        prompt = argv.index("-p", command + 1)
        argv[prompt + 1:prompt + 1] = ["--mode", "json"]
    started = time.monotonic()
    deadline = tick_deadline.get()
    tick_limited = deadline is not None and deadline - started <= timeout
    expires = started + timeout if deadline is None else min(started + timeout, deadline)
    output = {"stdout": bytearray(), "stderr": bytearray()}

    def collected(name: str) -> str:
        return output[name].decode(errors="replace").replace("\r\n", "\n").replace("\r", "\n")

    def expired() -> None:
        if tick_limited:
            raise TickExpired()
        raise subprocess.TimeoutExpired(argv, timeout, output=collected("stdout"), stderr=collected("stderr"))

    while True:
        if time.monotonic() >= expires:
            expired()
        attempt = time.monotonic()
        with _process(argv, cwd, env, input, expires=expires, expired=expired) as process:
            with selectors.DefaultSelector() as selector:
                for stream, name in ((process.stdout, "stdout"), (process.stderr, "stderr")):
                    assert stream is not None
                    os.set_blocking(stream.fileno(), False)
                    selector.register(stream, selectors.EVENT_READ, name)
                pending = memoryview(input.encode() if input is not None else b"")
                if process.stdin is not None:
                    if pending:
                        os.set_blocking(process.stdin.fileno(), False)
                        selector.register(process.stdin, selectors.EVENT_WRITE, "stdin")
                    else:
                        process.stdin.close()
                last_output = time.monotonic()
                while True:
                    now = time.monotonic()
                    if now >= expires or now - last_output >= PI_IDLE_SECONDS:
                        kill_process_groups([process.pid])
                        process.wait(timeout=5)
                        for key in list(selector.get_map().values()):
                            if key.data == "stdin":
                                continue
                            while True:
                                try:
                                    chunk = os.read(key.fd, 65536)
                                except BlockingIOError:
                                    break
                                if not chunk:
                                    break
                                output[key.data].extend(chunk)
                        if now >= expires:
                            expired()
                        log_event("call", call="pi", name="pi idle-retry",
                                  input={"argv": argv[command:], "stdin": input},
                                  output={"stdout": collected("stdout"), "stderr": collected("stderr"),
                                          "returncode": process.returncode}, started=attempt, ok=False)
                        break
                    if not selector.get_map() and process.poll() is not None:
                        return subprocess.CompletedProcess(argv, process.returncode, collected("stdout"), collected("stderr"))
                    for key, _ in selector.select(min(0.1, expires - now, PI_IDLE_SECONDS - (now - last_output))):
                        if key.data == "stdin":
                            try:
                                pending = pending[os.write(key.fd, pending[:65536]):]
                            except BrokenPipeError:
                                pending = memoryview(b"")
                            if not pending:
                                selector.unregister(key.fileobj)
                                cast(BinaryIO, key.fileobj).close()
                        else:
                            chunk = os.read(key.fd, 65536)
                            if chunk:
                                output[key.data].extend(chunk)
                                last_output = time.monotonic()
                            else:
                                selector.unregister(key.fileobj)


def pi_step(
    prompt: str,
    artifact: Path,
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float = 3600,
) -> dict[str, str]:
    worktree = cwd if cwd is not None else Path.cwd()
    child = pi_env(os.environ if env is None else env, worktree)
    provider = child.get("LOKAY2_PROVIDER", "")
    model = child.get("LOKAY2_MODEL", "")
    if not provider or not model:
        return {"result": "failed", "artifact": ""}
    from lokay.effects.git import PiGitViolation

    try:
        proc = run_process(
            sandboxed(["pi", "-p", "--mode", "json", "--provider", provider, "--model", model, prompt], worktree, child, artifact.parent.resolve()),
            cwd=cwd,
            env=child,
            timeout=timeout,
            retry="pi",
        )
    except PiGitViolation as exc:
        return exc.failure()
    if proc.returncode != 0 or not artifact.is_file() or artifact.stat().st_size == 0:
        return {"result": "failed", "artifact": ""}
    return {"result": "done", "artifact": str(artifact)}
