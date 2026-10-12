from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import subprocess


def _git(path: Path, *args: str, input: bytes | None = None) -> bytes:
    return subprocess.run(
        ["git", "-C", str(path), *args], input=input, capture_output=True, check=True,
    ).stdout


def _snapshot(path: Path) -> dict:
    status = _git(path, "status", "--porcelain", "-z", "--untracked-files=all")
    head = _git(path, "rev-parse", "HEAD").decode().strip()
    names = set(_git(path, "diff", "--name-only", "-z").split(b"\0"))
    names.update(_git(path, "diff", "--cached", "--name-only", "-z").split(b"\0"))
    # Keep both index and working-tree patches, including pre-existing edits.
    patches = {
        name.decode(): (
            _git(path, "diff", "--binary", "--cached", "--", name.decode()),
            _git(path, "diff", "--binary", "--", name.decode()),
        )
        for name in names if name
    }
    untracked = set(_git(path, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0")) - {b""}
    return {"status": status, "head": head, "patches": patches, "untracked": untracked}


def restore_changes(snapshots: dict[Path, dict]) -> dict:
    """Restore step changes and return the paths and files that were affected."""
    report = {"changed": False, "paths": [], "files": []}
    for path, before in snapshots.items():
        after = _snapshot(path)
        moved = after["head"] != before["head"]
        files = {
            name for name in before["patches"].keys() | after["patches"].keys()
            if before["patches"].get(name) != after["patches"].get(name)
        }
        if moved:
            files.update(name.decode() for name in _git(
                path, "diff", "--name-only", "-z", before["head"], after["head"],
            ).split(b"\0") if name)
        new = after["untracked"] - before["untracked"]
        changed = moved or after["status"] != before["status"] or bool(files)
        if not changed:
            continue
        report["changed"] = True
        report["paths"].append(str(path))
        report["files"].extend(f"{path}/{name}" for name in sorted(files | {n.decode() for n in new}))
        if moved and not before["status"]:
            _git(path, "reset", "--hard", before["head"])
        else:
            # Do not reset a dirty checkout's HEAD. Restore only affected files.
            for name in sorted(files):
                exists = subprocess.run(
                    ["git", "-C", str(path), "cat-file", "-e", f"{before['head']}:{name}"],
                    capture_output=True,
                ).returncode == 0
                if exists:
                    _git(path, "checkout", before["head"], "--", name)
                elif name.encode() in before["untracked"]:
                    _git(path, "rm", "--cached", "-f", "--ignore-unmatch", "--", name)
                else:
                    _git(path, "rm", "-f", "--ignore-unmatch", "--", name)
                staged, unstaged = before["patches"].get(name, (b"", b""))
                if staged:
                    _git(path, "apply", "--binary", "--index", input=staged)
                if unstaged:
                    _git(path, "apply", "--binary", input=unstaged)
        for name in sorted(new):
            _git(path, "--literal-pathspecs", "clean", "-fd", "--", name.decode())
    return report


@contextmanager
def guard(paths):
    """Yield a report populated on exit, including exceptional exits."""
    snapshots = {Path(path).expanduser().resolve(): None for path in paths if path is not None}
    snapshots = {path: _snapshot(path) for path in snapshots}
    report = {"changed": False, "paths": [], "files": []}
    try:
        yield report
    finally:
        report.update(restore_changes(snapshots))


def failure(report: dict, worktree: Path) -> dict:
    details = "; ".join(
        f"{path}: {', '.join(name.removeprefix(path + '/') for name in report['files'] if name.startswith(path + '/')) or 'HEAD/status'}"
        for path in report["paths"]
    )
    return {
        "result": "failed", "reason": "outside_worktree",
        "explanation": f"pi modified {details}; restored. Work only inside {worktree}.",
        "artifact": str(worktree),
    }
