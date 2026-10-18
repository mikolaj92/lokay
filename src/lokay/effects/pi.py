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
from collections.abc import Mapping, Sequence
from pathlib import Path
from subprocess import TimeoutExpired
from typing import Any, BinaryIO, cast

from lokay import store
from lokay.config import HOME
from lokay.effects.retry import retry


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
    from lokay.effects.git import git_try

    token = tick_deadline.set(None)
    try:
        for name in (".cache", ".validation"):
            directory = worktree / name
            if directory.is_symlink() or not directory.is_dir():
                continue
            code, out, err = git_try(worktree, "ls-files", "-z", "--", name, timeout=30)
            if code != 0:
                raise RuntimeError(err or "tracked cache lookup failed")
            if out:
                continue
            code, _, err = git_try(worktree, "check-ignore", "-q", "--", name + "/", timeout=30)
            if code == 0:
                shutil.rmtree(directory)
            elif code != 1:
                raise RuntimeError(err or "ignored cache lookup failed")
    finally:
        tick_deadline.reset(token)


def pi_env(base: Mapping[str, str], worktree: str | Path) -> dict[str, str]:
    from lokay.effects.git import git_try

    worktree = Path(worktree).resolve()
    code, out, _ = git_try(worktree, "rev-parse", "--git-common-dir", timeout=30)
    gitdir = (worktree / out.strip()).resolve() if code == 0 else worktree
    env = dict(base)
    for key in ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN",
                "GIT_ASKPASS", "SSH_AUTH_SOCK"):
        env.pop(key, None)
    temporary = Path(env.get("TMPDIR") or "/tmp").resolve()
    if temporary.is_relative_to(Path(worktree).resolve()):
        temporary = Path("/tmp").resolve()
    state = tempfile.mkdtemp(prefix="lokay-pi-", dir=temporary)
    cache = (Path(env.get("HOME") or Path.home()) / ".cache").resolve()
    if cache.is_relative_to(worktree):
        cache = Path(state) / "cache"
    for key, default in (("XDG_CACHE_HOME", cache), ("UV_CACHE_DIR", cache / "uv")):
        directory = (worktree / env[key]).resolve() if env.get(key) else default
        env[key] = str(default if directory.is_relative_to(worktree) else directory)
    env.update({
        "GH_CONFIG_DIR": state,
        "LOKAY_STATE_DIR": state,
        "XDG_STATE_HOME": state,
        "TMPDIR": state,
        "PATH": str(Path(__file__).resolve().parents[3] / "sandbox/bin") + os.pathsep + env.get("PATH", os.defpath),
        "LOKAY_PI_WORKTREE": str(worktree),
        "LOKAY_PI_GITDIR": str(gitdir),
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
    gitdir = env.get("LOKAY_PI_GITDIR") or pi_env({}, worktree)["LOKAY_PI_GITDIR"]
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


def run_process(
    argv: Sequence[str],
    *,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float | None = None,
    input: str | bytes | None = None,
    text: bool = True,
) -> subprocess.CompletedProcess[Any]:
    from lokay.store import log_event

    command = next((index for index, arg in enumerate(argv)
                    if Path(arg).name in ("gh", "git") or (Path(arg).name == "pi" and "-p" in argv[index + 1:])), None)
    if command is None:
        return _run_process(argv, cwd=cwd, env=env, timeout=timeout, input=input, text=text)
    call = Path(argv[command]).name
    started = time.monotonic()
    output = None
    ok = False
    attempts = []

    def execute():
        attempt = {}
        try:
            proc = _run_process(argv, cwd=cwd, env=env, timeout=timeout, input=input, text=text)
            attempt.update(argv=list(proc.args), returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)
            return proc
        except BaseException as exc:
            try:
                attempt.update(error=type(exc).__name__, reason=str(exc),
                               returncode=getattr(exc, "returncode", None),
                               stdout=getattr(exc, "stdout", None), stderr=getattr(exc, "stderr", None))
            except Exception:
                pass
            raise
        finally:
            try:
                attempts.append(store.redact({"argv": list(argv), "stdin": input, **attempt}, env))
            except Exception:
                pass

    try:
        if call != "pi":
            proc = execute()
        else:
            from lokay.effects.git import pi_git_guard

            with pi_git_guard(Path(cwd) if cwd is not None else Path.cwd()):
                def transient(proc):
                    if isinstance(proc, Exception) or proc.returncode == 0:
                        return None
                    match = re.search(
                        r"\b(?:401|429|5\d{2})\b|overloaded|rate[ _-]limit|ECONNRESET|Empty reply",
                        (proc.stdout or "") + "\n" + (proc.stderr or ""), re.IGNORECASE,
                    )
                    return match[0] if match else None

                proc = retry(execute, 4, transient, call="pi")
            proc.stdout = pi_assistant_text(proc.stdout)
        output = {"stdout": proc.stdout.decode(errors="replace") if isinstance(proc.stdout, bytes) else proc.stdout,
                  "stderr": proc.stderr.decode(errors="replace") if isinstance(proc.stderr, bytes) else proc.stderr,
                  "returncode": proc.returncode}
        ok = proc.returncode == 0
        return proc
    except BaseException as exc:
        output = {"error": type(exc).__name__, "reason": str(exc)}
        raise
    finally:
        log_event("call", call=call, name="pi -p" if call == "pi" else " ".join(argv[command + 1:command + 3])[:200],
                  input={"argv": list(argv[command:]),
                         "stdin": input.decode(errors="replace") if isinstance(input, bytes) else input},
                  output=output, started=started, ok=ok, _env=env,
                  effect={"argv": list(argv), "stdin": input, "attempts": attempts})


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
            held = store.acquire_lock(HOME / "pi-admission.lock")
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
    input: str | bytes | None = None,
    text: bool = True,
) -> subprocess.CompletedProcess[Any]:
    timeout = 3600 if timeout is None else timeout
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("process timeout must be finite and positive")
    timeout = min(timeout, 3600)
    deadline = tick_deadline.get()
    remaining = None if deadline is None else deadline - time.monotonic()
    if remaining is not None and remaining <= 0:
        raise TickExpired()
    if pi_command(argv) is not None:
        return _run_pi_process(argv, cwd=cwd, env=env, timeout=timeout, input=cast(str | None, input))
    with _process(argv, cwd, env, input, text=text) as process:
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
                                          "returncode": process.returncode}, started=attempt, ok=False, _env=env,
                                  effect={"argv": list(argv), "stdin": input,
                                          "attempts": [{"argv": list(argv), "stdin": input,
                                                        "stdout": collected("stdout"), "stderr": collected("stderr"),
                                                        "returncode": process.returncode}]})
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


def run_pi(
    worktree: Path,
    prompt: str,
    clone_path: Path | str | None = None,
    *,
    env: Mapping[str, str],
    cwd: Path | None,
    timeout: float = 3600,
    extra_dir: Path | None = None,
    guarded: bool = True,
    json_mode: bool = False,
    missing_is_failure: bool = False,
) -> subprocess.CompletedProcess[Any] | dict:
    from lokay.effects.git import PiGitViolation, failure, guard

    argv = ["pi", "-p"]
    if json_mode:
        argv += ["--mode", "json"]
    argv += ["--provider", env.get("LOKAY2_PROVIDER", ""), "--model", env.get("LOKAY2_MODEL", ""), prompt]
    guard_paths = [Path(__file__).resolve().parents[3], clone_path] if guarded else None
    changes = {"changed": False}
    try:
        with (guard(guard_paths) if guard_paths is not None else nullcontext(changes)) as changes:
            proc = run_process(
                sandboxed(argv, worktree, env, extra_dir),
                cwd=cwd,
                env=env,
                timeout=timeout,
            )
    except Exception as exc:
        if isinstance(exc, PiGitViolation):
            return exc.failure()
        if changes["changed"]:
            return failure(changes, worktree)
        if missing_is_failure and isinstance(exc, FileNotFoundError):
            return {"result": "failed", "artifact": ""}
        raise
    finally:
        if guard_paths is not None:
            cleanup_worktree_caches(worktree)
    if changes["changed"]:
        return failure(changes, worktree)
    return proc


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
    from lokay import store

    store.ensure_directory(artifact.parent)
    proc = run_pi(
        worktree,
        prompt,
        env=child,
        cwd=cwd,
        timeout=timeout,
        extra_dir=artifact.parent.resolve(),
        guarded=False,
        json_mode=True,
    )
    if isinstance(proc, dict):
        return proc
    if proc.returncode != 0 or not artifact.is_file() or artifact.stat().st_size == 0:
        return {"result": "failed", "artifact": ""}
    return {"result": "done", "artifact": str(artifact)}
