"""One job: detach a live issue_to_pr child and persist its receipt."""

from __future__ import annotations

import fcntl
import json
import os
import secrets
import signal
import subprocess
import sys
import time
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any


_ACTIVATION_PROTOCOL = "pipe-v1"


def issue_to_pr_log_path(repo: str, number: int) -> Path:
    slug = str(repo).replace("/", "__")
    root = Path.home() / ".lokay" / "logs"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"issue-to-pr-{slug}-{int(number)}.log"


def issue_to_pr_receipt_path(repo: str, number: int) -> Path:
    slug = str(repo).replace("/", "__")
    root = Path.home() / ".lokay" / "cycle"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{slug}-{int(number)}.json"


@contextmanager
def _receipt_write_lock(path: Path):
    """Serialize all transitions over the receipt name, not its inode."""
    lock_path = path.parent / ".issue-to-pr-receipts.lock"
    try:
        with lock_path.open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    except OSError as exc:
        raise OSError(f"cannot lock issue_to_pr receipts: {exc}") from exc


def _starting_receipt_state(payload: dict[str, Any]) -> str:
    """Return ``live``, ``orphaned``, or ``unknown`` without trusting absence.

    Only pipe-gated reservations can be reclaimed. Their child holds only the
    read end before activation, so launcher death closes the write end and
    makes it exit before it can start Fala or touch a worktree. Old
    reservations predate that guarantee and deliberately retain their lane.
    """
    if payload.get("activation") != _ACTIVATION_PROTOCOL:
        return "live"
    try:
        launcher_pid = int(payload["launcher_pid"])
    except (KeyError, TypeError, ValueError):
        return "unknown"
    if launcher_pid <= 0:
        return "unknown"
    return "live" if pid_is_alive(launcher_pid) else "orphaned"


def _write_starting_receipt(path: Path, payload: dict[str, Any]) -> Path:
    """Reserve a receipt name once, before any child may be spawned."""
    with _receipt_write_lock(path):
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            # Completed/dead PID receipts are historical and replaceable. A
            # reservation remains until its pipe-gated launcher is proven dead;
            # malformed/legacy state is deliberately not ownership evidence.
            try:
                previous = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise OSError(f"cannot inspect existing issue_to_pr receipt: {exc}") from exc
            if not isinstance(previous, dict):
                raise OSError("existing issue_to_pr receipt is not an object")
            if previous.get("starting") is True:
                state = _starting_receipt_state(previous)
                if state != "orphaned":
                    detail = "still starting" if state == "live" else "state is unknown"
                    raise OSError(f"existing issue_to_pr receipt is {detail}")
            elif previous.get("pid") is not None:
                try:
                    previous_pid = int(previous["pid"])
                except (TypeError, ValueError):
                    raise OSError("existing issue_to_pr receipt has an invalid pid") from None
                if is_live_issue_to_pr_pid(previous_pid):
                    raise OSError("existing issue_to_pr receipt is still live")
            else:
                raise OSError("existing issue_to_pr receipt has no pid")
            try:
                path.unlink()
            except OSError as exc:
                raise OSError(f"cannot clear completed issue_to_pr receipt: {exc}") from exc
            try:
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError as exc:
                raise OSError("issue_to_pr reservation was claimed concurrently") from exc
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
                fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())
        except BaseException:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
            raise
    return path


def write_issue_to_pr_receipt(payload: dict[str, Any]) -> Path:
    """Atomically reserve or publish an issue-to-PR lifecycle receipt."""
    path = issue_to_pr_receipt_path(str(payload["repo"]), int(payload["issue"]))
    if payload.get("starting") is True:
        return _write_starting_receipt(path, payload)

    # Hold the stable sidecar lock through matching ownership verification and
    # replacement: replacing a path changes its inode, so receipt-file locking
    # would permit a second launcher to be overwritten between read and rename.
    launch_id = str(payload.get("launch_id") or "")
    with _receipt_write_lock(path):
        if launch_id:
            try:
                previous = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise OSError(f"cannot inspect starting issue_to_pr receipt: {exc}") from exc
            if not isinstance(previous, dict) or previous.get("launch_id") != launch_id:
                raise OSError("issue_to_pr reservation ownership changed")
        temp = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
        try:
            with temp.open("x", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
                fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(temp, path)
        except BaseException:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass
            raise
    return path


def _discard_starting_receipt(path: Path, launch_id: str) -> bool:
    """Drop only this launch's reservation after its process group is gone."""
    try:
        with _receipt_write_lock(path):
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("launch_id") != launch_id:
                return False
            path.unlink()
    except (OSError, ValueError):
        return False
    return True

def _terminate_detached_process_group(proc: Any, *, timeout_seconds: float = 5.0) -> bool:
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

    return _terminate_detached_process_group(_Proc(pid), timeout_seconds=timeout_seconds)


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


def _is_cycle_start_metric(data: dict[str, Any], path: Path | None) -> bool:
    """Require the complete metric schema and its distinct filename."""
    repo = data.get("repo")
    issue = data.get("issue")
    started_ts = data.get("started_ts")
    if (
        not isinstance(repo, str)
        or repo.strip() != repo
        or repo.count("/") != 1
        or any(not part for part in repo.split("/"))
        or isinstance(issue, bool)
        or not isinstance(issue, int)
        or issue < 1
        or not isinstance(started_ts, str)
        or len(started_ts) != 20
    ):
        return False
    try:
        parsed_started_ts = datetime.strptime(started_ts, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    if parsed_started_ts.strftime("%Y-%m-%dT%H:%M:%SZ") != started_ts:
        return False
    owner, name = repo.split("/", 1)
    expected_name = f"{owner}__{name}__{issue}.json"
    return path is None or path.name == expected_name


def _has_issue_identity(data: dict[str, Any]) -> bool:
    try:
        issue = int(data.get("issue"))
    except (TypeError, ValueError):
        return False
    return isinstance(data.get("repo"), str) and bool(data["repo"]) and issue > 0


def _receipt_is_readable(data: Any, path: Path | None = None) -> bool:
    """Validate lifecycle state without misreading malformed JSON as a metric."""
    if not isinstance(data, dict):
        return False
    if data.get("starting") is True:
        # Starting records must identify their lane. A malformed lifecycle
        # reservation is uncertainty, not an idle cycle file. Legacy records
        # with a complete identity stay occupied but are never reclaimed.
        try:
            issue = int(data.get("issue"))
        except (TypeError, ValueError):
            return False
        if (
            not isinstance(data.get("launch_id"), str)
            or not data["launch_id"]
            or not isinstance(data.get("repo"), str)
            or not data["repo"]
            or issue < 1
        ):
            return False
        if "activation" not in data:
            return True
        return _starting_receipt_state(data) != "unknown"
    if "starting" in data:
        return False
    if "pid" not in data:
        # Failed/reaped receipts (ok=false + identity) are idle, not unknown.
        if data.get("ok") is False and _has_issue_identity(data):
            return True
        return _is_cycle_start_metric(data, path)
    try:
        pid = int(data["pid"])
    except (TypeError, ValueError):
        return False
    # pid 0 / negative is a finished or reclaimable receipt, not unknown.
    if pid <= 0:
        return _has_issue_identity(data)
    return (
        _has_issue_identity(data)
        and (
            "launch_id" not in data
            or (isinstance(data["launch_id"], str) and bool(data["launch_id"]))
        )
    )


def has_unreadable_issue_to_pr_receipts(cycle_dir: Path | None = None) -> bool:
    """Whether lifecycle state is unknown and destructive work must pause."""
    root = Path(cycle_dir) if cycle_dir is not None else Path.home() / ".lokay" / "cycle"
    try:
        with os.scandir(root) as entries:
            paths = sorted(
                (Path(entry.path) for entry in entries if entry.name.endswith(".json")),
                key=lambda path: path.name,
            )
    except FileNotFoundError:
        return False
    except OSError:
        return True
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return True
        if not _receipt_is_readable(data, path):
            return True
    return False

def live_issue_to_pr_receipts(
    cycle_dir: Path | None = None,
    *,
    pid_alive=None,
) -> list[dict[str, Any]]:
    """Live or launching receipts that must keep a repo occupied."""
    root = Path(cycle_dir) if cycle_dir is not None else Path.home() / ".lokay" / "cycle"
    check = pid_alive or is_live_issue_to_pr_pid
    if not root.is_dir():
        return []
    live: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        if not data.get("repo") or data.get("issue") is None:
            continue
        # A reservation remains occupancy until its matching PID receipt is
        # published. Pipe-gated reservations whose launcher died before
        # activation are inert and can be recovered by the next dispatcher.
        if data.get("starting") is True:
            if _starting_receipt_state(data) != "orphaned":
                live.append(data)
            continue
        if "pid" not in data:
            continue
        try:
            pid = int(data["pid"])
            issue = int(data["issue"])
        except (TypeError, ValueError):
            continue
        if check(pid) or coding_live_for_issue(issue):
            live.append(data)
    return live


def clear_dead_issue_to_pr_receipts(
    repos: Iterable[str],
    cycle_dir: Path | None = None,
    *,
    pid_alive=None,
) -> list[dict[str, Any]]:
    """Remove finished issue-to-PR receipts after a repo's PR was merged.

    A receipt is the harvest record for a detached child, so only a receipt
    whose wrapper and issue coder are both gone is safe to remove. In
    particular, a dead wrapper does not prove that a still-running pi is
    finished; keep that receipt until the open issue's coder exits.
    """
    root = Path(cycle_dir) if cycle_dir is not None else Path.home() / ".lokay" / "cycle"
    repo_names = {str(repo) for repo in repos if str(repo)}
    check = pid_alive or is_live_issue_to_pr_pid
    if not repo_names or not root.is_dir():
        return []

    cleared: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        try:
            with _receipt_write_lock(path):
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, dict) or data.get("repo") not in repo_names:
                    continue
                # Metric receipts and pipe-gated reservations are not detached
                # child receipts. Leave them for their owning lifecycle atom.
                if data.get("starting") is True or "pid" not in data:
                    continue
                pid = int(data["pid"])
                issue = int(data["issue"])
                if pid > 0 and (check(pid) or coding_live_for_issue(issue)):
                    continue
                path.unlink()
                cleared.append(data)
        except (FileNotFoundError, OSError, TypeError, ValueError):
            # A concurrent lifecycle transition or malformed receipt is not
            # evidence that a live worker is safe to remove.
            continue
    return cleared


def detach_issue_to_pr(
    *,
    repo: str,
    issue: int,
    config_path: str | None,
    popen=None,
) -> dict[str, Any]:
    """Detach only after a durable receipt and child activation barrier.

    The child blocks on a private pipe before it can run Fala. If this parent
    dies after ``Popen`` but before final publication, its write end closes and
    the child exits without touching a worktree. That makes a later recovery
    of the pre-spawn reservation safe rather than a second-worker race.
    """
    spawn = popen or subprocess.Popen
    repo_name = str(repo)
    issue_number = int(issue)
    argv = [sys.executable, "-u", "-m", "lokay.compose.issue_to_pr"]
    if config_path:
        argv.extend(["--config", str(config_path)])
    argv.extend(["--live", "--repo", repo_name, "--issue", str(issue_number)])
    root = os.environ.get("LOKAY_ROOT") or str(Path.cwd())
    env = os.environ.copy()
    root = env.get("LOKAY_ROOT") or str(Path.cwd())
    if not env.get("LOKAY_PROCESS_HEAD"):
        from lokay.git_host_ff import snapshot_process_head
        snapshot_process_head(Path(root))
        if os.environ.get("LOKAY_PROCESS_HEAD"):
            env["LOKAY_PROCESS_HEAD"] = os.environ["LOKAY_PROCESS_HEAD"]
    if not env.get("LOKAY_HEALTH_LEASE"):
        from lokay.preflight import issue_health_lease
        issue_health_lease()
        for key in ("LOKAY_HEALTH_LEASE", "LOKAY_HEALTH_LEASE_PATH"):
            if os.environ.get(key):
                env[key] = os.environ[key]
    if env.get("LOKAY_HEALTH_LEASE") and not env.get("LOKAY_HEALTH_LEASE_PATH"):
        env["LOKAY_HEALTH_LEASE_PATH"] = str(Path.home() / ".lokay" / "health-lease")

    log_path = issue_to_pr_log_path(repo_name, issue_number)
    launch_id = secrets.token_hex(16)
    starting = {
        "ok": True,
        "detached": False,
        "starting": True,
        "activation": _ACTIVATION_PROTOCOL,
        "launch_id": launch_id,
        "launcher_pid": os.getpid(),
        "repo": repo_name,
        "issue": issue_number,
        "log": str(log_path),
    }
    try:
        receipt_path = write_issue_to_pr_receipt(starting)
    except OSError as exc:
        return {
            "ok": False,
            "reason": "receipt_unavailable",
            "error": f"cannot reserve issue_to_pr receipt: {exc}",
            "repo": repo_name,
            "issue": issue_number,
        }

    try:
        read_fd, write_fd = os.pipe()
    except OSError as exc:
        _discard_starting_receipt(receipt_path, launch_id)
        return {
            "ok": False,
            "reason": "activation_unavailable",
            "error": f"cannot create issue_to_pr activation pipe: {exc}",
            "repo": repo_name,
            "issue": issue_number,
        }
    env["LOKAY_ISSUE_TO_PR_ACTIVATION_FD"] = str(read_fd)
    try:
        log_fh = log_path.open("ab")
    except OSError as exc:
        os.close(read_fd)
        os.close(write_fd)
        _discard_starting_receipt(receipt_path, launch_id)
        return {
            "ok": False,
            "reason": "log_unavailable",
            "error": f"cannot open issue_to_pr log: {exc}",
            "repo": repo_name,
            "issue": issue_number,
        }
    try:
        proc = spawn(
            argv,
            cwd=root,
            env=env,
            start_new_session=True,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            pass_fds=(read_fd,),
        )
    except OSError as exc:
        os.close(read_fd)
        os.close(write_fd)
        _discard_starting_receipt(receipt_path, launch_id)
        return {
            "ok": False,
            "reason": "spawn_failed",
            "error": f"cannot start issue_to_pr: {exc}",
            "repo": repo_name,
            "issue": issue_number,
        }
    finally:
        log_fh.close()

    receipt = {
        "ok": True,
        "detached": True,
        "pid": int(proc.pid),
        "repo": repo_name,
        "issue": issue_number,
        "log": str(log_path),
        "launch_id": launch_id,
    }
    try:
        receipt["receipt"] = str(write_issue_to_pr_receipt(receipt))
    except OSError as exc:
        os.close(read_fd)
        os.close(write_fd)
        terminated = _terminate_detached_process_group(proc)
        if terminated:
            _discard_starting_receipt(receipt_path, launch_id)
        return {
            "ok": False,
            "reason": "receipt_unavailable",
            "error": f"cannot publish issue_to_pr receipt: {exc}",
            "repo": repo_name,
            "issue": issue_number,
            "pid": int(proc.pid),
            "cleanup_confirmed": terminated,
        }
    try:
        os.write(write_fd, b"1")
    except OSError as exc:
        # The receipt is durable but a child that never read activation cannot
        # work; terminate conservatively and leave its final historical receipt.
        terminated = _terminate_detached_process_group(proc)
        return {
            "ok": False,
            "reason": "activation_unavailable",
            "error": f"cannot release issue_to_pr child: {exc}",
            "repo": repo_name,
            "issue": issue_number,
            "pid": int(proc.pid),
            "cleanup_confirmed": terminated,
        }
    finally:
        os.close(read_fd)
        os.close(write_fd)
    return receipt
