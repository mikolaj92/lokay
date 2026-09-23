"""Fail-closed macOS seatbelt for one coding worker. Not a second framework."""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path


def _path(path: Path) -> str:
    value = str(path.resolve())
    if value.startswith("/var/"):
        value = "/private" + value
    return value


def coding_profile(*, worktree: Path, scratch: Path, executable: Path | None) -> str:
    root = _path(worktree)
    private = _path(scratch)
    binary = _path(executable) if executable else ""
    # The interpreter lives outside the worktree (uv/pyenv/venv). Read and exec
    # of its own prefix, and read of the worktree's ancestors (a checkout's
    # .venv sits above it), is the worker, not an escape. Writes stay inside.
    # A bare name PATH does not carry has no prefix, so it gets no exec grant.
    runtime = _path(executable.parent.parent) if executable else ""
    ancestors = _path(worktree.resolve().parent)
    harness = [
        f'(allow process-exec (literal "{binary}"))',
        f'(allow process-exec (subpath "{runtime}"))',
        f'(allow file-read* (subpath "{runtime}"))',
    ] if executable else []
    gitconfig = Path.home() / ".gitconfig"
    # The harness reads its own model catalog and credentials from its home.
    # Lokay does not supply either, so the seatbelt only grants the read.
    harness_state = Path.home() / ".pi"
    # Local git (commit inside the worktree) is an edit. Publication is not:
    # network stays on localhost, so push/fetch have no route out.
    return "\n".join([
        "(version 1)",
        "(deny default)",
        '(import "system.sb")',
        *harness,
        f'(allow file-read* (subpath "{ancestors}"))',
        *( [f'(allow file-read* (literal "{_path(gitconfig)}"))'] if gitconfig.is_file() else [] ),
        *( [f'(allow file-read* (subpath "{_path(harness_state)}"))'] if harness_state.is_dir() else [] ),
        '(allow process-exec (subpath "/usr/bin"))',
        '(allow process-exec (subpath "/bin"))',
        '(allow process-exec (subpath "/usr/local/bin"))',
        "(allow process-fork)",
        "(allow signal (target self))",
        "(allow sysctl-read)",
        '(allow file-read* (subpath "/usr"))',
        '(allow file-read* (subpath "/System"))',
        '(allow file-read* (subpath "/Library"))',
        '(allow process-exec (subpath "/Library/Developer/CommandLineTools"))',
        '(allow file-write* (regex #"^/private/var/folders/.*/xcrun_db-"))',
        '(allow file-read* (subpath "/opt/homebrew"))',
        '(allow process-exec (subpath "/opt/homebrew"))',
        '(allow file-read* (subpath "/bin"))',
        '(allow file-read* (subpath "/sbin"))',
        '(allow file-read* (subpath "/private/var/db/dyld"))',
        '(allow file-read* (subpath "/private/var/select"))',
        '(allow file-read* (subpath "/private/var/db/xcode_select_link"))',
        '(allow file-read* (subpath "/dev"))',
        '(allow file-read* (subpath "/private/etc"))',
        '(allow file-read-metadata file-test-existence (subpath "/Users"))',
        f'(allow file-read* file-write* (subpath "{root}"))',
        f'(allow file-read* file-write* (subpath "{private}"))',
        '(allow network-outbound (remote tcp "localhost:*"))',
        "",
    ])


def coding_argv(argv: list[str], *, worktree: Path) -> tuple[list[str], Path]:
    if sys.platform != "darwin":
        raise ValueError("sandbox_runtime_unsupported")
    sandbox = Path("/usr/bin/sandbox-exec")
    if not sandbox.is_file():
        raise ValueError("sandbox_runtime_unsupported")
    if not argv or not argv[0]:
        raise ValueError("sandbox_runtime_unsupported")
    named = argv[0]
    if "/" not in named:
        # A bare command found on PATH is the harness. Resolving it against cwd
        # names a file in the repo (lokay/pi) that was never installed. A name
        # PATH does not carry stays bare, so the exec fails closed on the name
        # instead of on an invented path.
        found = shutil.which(named)
        executable = Path(found).resolve() if found else None
    else:
        executable = Path(named).resolve()
    # sandbox-exec canonicalises the exec path, so the profile must name the
    # real interpreter, not a venv symlink that points outside the prefix.
    argv = [str(executable) if executable else named, *argv[1:]]
    scratch = Path(tempfile.mkdtemp(prefix="lokay-coding-")).resolve()
    profile = scratch / "coding.sb"
    profile.write_text(coding_profile(worktree=worktree, scratch=scratch, executable=executable))
    wrapped = [str(sandbox), "-f", str(profile), "--", *argv]
    return wrapped, scratch
